"""知識點標記與弱點分析。

AI 依科目標記：先讀這科所有題目的摘要整理出知識點清單（約每 5 題一個，4～15 個，粒度約一章），
再分批（每批 topic_batch_size 題）把每題歸到 1～2 個知識點。之後再匯入新題目時沿用同一份清單。
弱點＝作答次數達 topic_weak_min_attempts 且正確率低於 topic_weak_accuracy 的知識點。
"""

import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import UTC, datetime
from threading import Lock

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.text import match_key, strip_edge_punct
from app.modules.ai import service as ai_service
from app.modules.bank import service as bank_service
from app.modules.bank.schemas import QuestionFilter, QuestionOut
from app.modules.review import service as review_service
from app.modules.topics.models import TopicTag
from app.modules.topics.schemas import SubjectTopics, TagRequest, TagResult, TopicsOverview, TopicStat, WeakTopic

OTHER = "其他"
ALL_TYPES = ["single_choice", "multi_choice", "essay"]
"""申論題也標知識點：申論題的自評結果一樣會算進弱點"""
TAXONOMY_SAMPLE = 120
"""整理知識點清單時最多讀幾題的摘要（超過就平均抽樣）"""

TAXONOMY_SYSTEM = """你是台灣國家考試的命題分析老師。根據使用者提供的某一科考題摘要，整理這一科的「知識點」清單，用來分析考生的弱點。
只輸出 JSON 物件，不要其他文字或程式碼框：{"topics": ["...", "..."]}
規則：
- 知識點數量照使用者指定的數量（可以差 2 個以內），涵蓋所有題目。
- 粒度約等於教科書的一章（例如「行政處分」「作業系統」「計算機網路」「數位影像處理」），每個知識點至少要對應 3 題；寧可粗一點，不要細到只對應一兩題。
- 不要太廣到等於整個科目。
- 一份試卷混合多個領域時（例如法學知識與英文），每個領域分開整理。
- 名稱用繁體中文（專有名詞可保留英文），2 到 12 個字，不要編號。
- 如果有提供已有的知識點，合理的請沿用原名稱。"""

CLASSIFY_SYSTEM = """你是台灣國家考試的命題分析老師。把每一題歸到知識點清單中最相關的 1 到 2 個知識點。
只輸出 JSON 物件，不要其他文字或程式碼框：{"tags": {"題目編號": ["知識點", ...]}}
規則：
- 知識點名稱必須和清單完全一致；真的都不符合才用「其他」。
- 每一題都要有結果，題目編號用方括號裡的數字。"""


class TopicsError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _parse_json(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    # 從每個「{」試著解析一個完整的 JSON 物件；JSON 後面多一句含大括號的說明也讀得到前面那段
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", cleaned):
        try:
            payload, _ = decoder.raw_decode(cleaned, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise TopicsError("AI 回傳的格式看不懂，請再試一次", 502)


_NAME_SEPARATORS = re.compile(r"[、，,；;\n]+")


def _names(value: object) -> list[str]:
    """AI 給的知識點名稱：陣列照用；字串（例如「行政處分、比例原則」）依頓號、逗號、分號切開，不能逐字走過。"""
    if isinstance(value, str):
        return [name for name in _NAME_SEPARATORS.split(value) if name.strip()]
    if isinstance(value, list):
        return [name for name in value if isinstance(name, str)]
    return []


def _complete(db: Session, feature: str, system: str, prompt: str) -> str:
    try:
        return ai_service.complete(db, feature, system, prompt).text
    except ai_service.AiUnavailable as error:
        raise TopicsError(str(error), 503) from error


def _topic_key(name: str) -> str:
    """知識點名稱的比對鍵：不分全形半形、大小寫、空白與前後標點（TCP/IP＝ＴＣＰ／ＩＰ、作業系統＝作業系統。）。"""
    return match_key(name, strip_punct=True, keep_spaces=False)


def _topic_name(text: str) -> str:
    """AI 給的知識點名稱整理成顯示用：全形英數轉半形、去掉前後標點。"""
    return strip_edge_punct(_clean(unicodedata.normalize("NFKC", text), 30))


def _clean(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _summary(question: QuestionOut) -> str:
    stem = question.stem
    if question.passage and len(stem) < 40:  # 克漏字等題組，題幹太短，補上文章開頭
        stem = f"{stem}（文章：{_clean(question.passage, 80)}）"
    return _clean(stem, 90)


def _sample(items: list, limit: int) -> list:
    if len(items) <= limit:
        return items
    step = len(items) / limit
    return [items[int(index * step)] for index in range(limit)]


def _subject_topics(db: Session, subject: str) -> list[str]:
    rows = db.scalars(select(TopicTag.topic).where(TopicTag.subject == subject).distinct().order_by(TopicTag.topic))
    return [topic for topic in rows if topic != OTHER]


def _build_taxonomy(db: Session, subject: str, questions: list[QuestionOut], existing: list[str]) -> list[str]:
    target = min(max(round(len(questions) / 5), 4), 15)
    lines = [
        f"科目：{subject}（共 {len(questions)} 題）",
        f"請整理成約 {target} 個知識點。",
        f"已有的知識點：{'、'.join(existing) if existing else '（無）'}",
        "",
        "題目摘要：",
    ]
    lines += [f"- {_summary(question)}" for question in _sample(questions, TAXONOMY_SAMPLE)]
    payload = _parse_json(_complete(db, "topics_taxonomy", TAXONOMY_SYSTEM, "\n".join(lines)))
    topics: list[str] = []
    keys = {_topic_key(OTHER)}
    for topic in _names(payload.get("topics")):
        if (name := _topic_name(topic)) and (key := _topic_key(name)) not in keys:
            keys.add(key)
            topics.append(name)
    if not topics:
        raise TopicsError("AI 沒有整理出知識點，請再試一次", 502)
    return topics


def _classify(db: Session, subject: str, topics: list[str], batch: list[QuestionOut]) -> dict[int, list[str]]:
    lines = [f"科目：{subject}", f"知識點清單：{'、'.join(topics)}", ""]
    for index, question in enumerate(batch, start=1):
        lines.append(f"[{index}] {_clean(question.stem, 220)}")
        if question.passage and len(question.stem) < 40:
            lines.append(f"文章開頭：{_clean(question.passage, 120)}")
        if question.options:
            lines.append(f"選項：{' ／ '.join(_clean(option, 40) for option in question.options)}")
    payload = _parse_json(_complete(db, "topics_classify", CLASSIFY_SYSTEM, "\n".join(lines)))
    raw = payload.get("tags") if isinstance(payload.get("tags"), dict) else {}
    # 題號有時會寫成 "[1]"、"1." 之類；知識點名稱比對時忽略空白、全形半形與前後標點
    by_index = {int(match[0]): names for key, names in raw.items() if (match := re.search(r"\d+", str(key)))}
    allowed = {_topic_key(topic): topic for topic in topics}

    result = {}
    for index, question in enumerate(batch, start=1):
        names = _names(by_index.get(index))
        # 清單裡太長的名稱存的是截斷後的版本，AI 回原本的全名時也要對得上
        picked = [allowed[key] for name in names if (key := _topic_key(_topic_name(name))) in allowed]
        result[question.id] = list(dict.fromkeys(picked))[:2] or [OTHER]
    return result


# 同一科一次只標一次：兩個分頁同時按「標記」時，後到的等前一個做完，題目都標好了就不再花用量。
_subject_locks: defaultdict[str, Lock] = defaultdict(Lock)
_subject_locks_guard = Lock()


def _subject_lock(subject: str) -> Lock:
    with _subject_locks_guard:
        return _subject_locks[subject]


def tag_subject(db: Session, data: TagRequest) -> TagResult:
    """用 AI 幫一個科目的題目標知識點。已標過的題目會略過（retag 時重來）。"""
    with _subject_lock(data.subject):
        db.expire_all()
        return _tag_subject(db, data)


def _tag_subject(db: Session, data: TagRequest) -> TagResult:
    ids = bank_service.query_question_ids(db, QuestionFilter(subject=data.subject, types=ALL_TYPES))
    if not ids:
        raise TopicsError("找不到這個科目的題目", 404)
    # 試卷重新匯入時改了科目名稱：這些題目的標記還掛在舊科目名稱下，改成現在的名稱，
    # 知識點清單才會接續使用、重新標記也清得掉
    db.execute(
        update(TopicTag).where(TopicTag.question_id.in_(ids), TopicTag.subject != data.subject).values(subject=data.subject)
    )
    db.commit()

    # 重新標記：舊的 AI 標記先留著，全部分類完才一次換掉；AI 關閉、額度用完或回傳看不懂時，原本的標記都還在
    old_ai_tags = (
        or_(TopicTag.subject == data.subject, TopicTag.question_id.in_(ids)),
        TopicTag.source == "ai",
    )
    if data.retag:
        kept = set(db.scalars(select(TopicTag.question_id).where(TopicTag.question_id.in_(ids), TopicTag.source != "ai")))
        todo = [qid for qid in ids if qid not in kept]
        existing = [
            topic
            for topic in db.scalars(
                select(TopicTag.topic).where(TopicTag.subject == data.subject, TopicTag.source != "ai").distinct().order_by(TopicTag.topic)
            )
            if topic != OTHER
        ]
    else:
        tagged = set(db.scalars(select(TopicTag.question_id).where(TopicTag.question_id.in_(ids))))
        todo = [qid for qid in ids if qid not in tagged]
        existing = _subject_topics(db, data.subject)
    if not todo:
        return TagResult(subject=data.subject, tagged=0, topics=existing, calls=0)

    calls = 0
    topics = existing
    if not topics:
        topics = _build_taxonomy(db, data.subject, bank_service.get_questions(db, ids), existing)
        calls += 1

    questions = bank_service.get_questions(db, todo)
    size = max(get_settings().topic_batch_size, 1)
    pending: list[TopicTag] = []
    for start in range(0, len(questions), size):
        result = _classify(db, data.subject, topics, questions[start : start + size])
        calls += 1
        now = _now()
        tags = [
            TopicTag(question_id=question_id, subject=data.subject, topic=name, source="ai", created_at=now)
            for question_id, names in result.items()
            for name in names
        ]
        if data.retag:
            pending += tags
        else:
            db.add_all(tags)
            db.commit()  # 每批都存起來，後面失敗也不會白花前面的用量
    if data.retag:
        db.execute(delete(TopicTag).where(*old_ai_tags))
        db.add_all(pending)
        db.commit()
    return TagResult(subject=data.subject, tagged=len(questions), topics=topics, calls=calls)


def _stat(topic: str, question_ids: list[int], stats: dict) -> TopicStat:
    settings = get_settings()
    answered = [stats[qid] for qid in question_ids if qid in stats]
    attempts = sum(item.attempts for item in answered)
    correct = sum(item.correct for item in answered)
    accuracy = round(correct / attempts, 4) if attempts else None
    return TopicStat(
        topic=topic,
        questions=len(question_ids),
        answered=len(answered),
        attempts=attempts,
        correct=correct,
        accuracy=accuracy,
        wrong_book=sum(1 for item in answered if item.in_wrong_book),
        weak=accuracy is not None
        and attempts >= settings.topic_weak_min_attempts
        and accuracy < settings.topic_weak_accuracy,
        question_ids=question_ids,
    )


def _order(stat: TopicStat) -> tuple:
    # 「其他」固定排最後，其餘弱點優先、正確率低的在前
    return (stat.topic == OTHER, not stat.weak, stat.accuracy if stat.accuracy is not None else 2.0, -stat.questions)


def overview(db: Session) -> TopicsOverview:
    settings = get_settings()
    batch = max(settings.topic_batch_size, 1)
    subjects = []
    weak = []
    for subject in bank_service.get_filter_options(db).subjects:
        ids = bank_service.query_question_ids(db, QuestionFilter(subject=subject, types=ALL_TYPES))
        if not ids:
            continue
        by_topic: dict[str, list[int]] = defaultdict(list)
        tagged = set()
        for question_id, topic in db.execute(
            select(TopicTag.question_id, TopicTag.topic).where(TopicTag.question_id.in_(ids)).order_by(TopicTag.question_id)
        ):
            by_topic[topic].append(question_id)
            tagged.add(question_id)
        stats = review_service.question_stats(db, ids)
        topics = sorted((_stat(topic, qids, stats) for topic, qids in by_topic.items()), key=_order)
        untagged = len(ids) - len(tagged)
        subjects.append(
            SubjectTopics(
                subject=subject,
                questions=len(ids),
                tagged=len(tagged),
                # 標記時只沿用「其他」以外的知識點清單；全部都是「其他」時還要再整理一次清單
                estimated_calls=math.ceil(untagged / batch) + (0 if any(topic != OTHER for topic in by_topic) else 1)
                if untagged
                else 0,
                topics=topics,
            )
        )
        weak += [WeakTopic(subject=subject, **stat.model_dump()) for stat in topics if stat.weak]
    weak.sort(key=lambda stat: (stat.accuracy or 0.0, -stat.attempts))
    return TopicsOverview(
        subjects=subjects,
        weak=weak,
        weak_accuracy=settings.topic_weak_accuracy,
        weak_min_attempts=settings.topic_weak_min_attempts,
    )
