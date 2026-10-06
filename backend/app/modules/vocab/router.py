from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.vocab import service
from app.modules.vocab.importer import ImportFormatError
from app.modules.vocab.schemas import (
    AnswerIn,
    AnswerResult,
    BuiltinList,
    DailyQuiz,
    ImportResult,
    QuizItem,
    VocabStats,
    WordOut,
    WordPage,
    WordStatus,
)

router = APIRouter(tags=["vocab"])


@router.get("/daily", response_model=DailyQuiz)
def daily(db: Session = Depends(get_db)) -> DailyQuiz:
    """今天的每日複習（第一次呼叫時抽題，當天固定不變）。"""
    return service.get_daily(db)


@router.get("/quiz", response_model=list[QuizItem])
def practice_quiz(source: service.QuizSource = "wrong", count: int = 10, db: Session = Depends(get_db)) -> list[QuizItem]:
    """自由練習。source=wrong 是錯題單字集中複習。"""
    return service.build_quiz(db, source, count)


@router.post("/answers", response_model=AnswerResult)
def answer(data: AnswerIn, db: Session = Depends(get_db)) -> AnswerResult:
    try:
        return service.answer(db, data)
    except service.VocabError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error


@router.get("/words", response_model=WordPage)
def list_words(
    search: str | None = None,
    tag: str | None = None,
    status: WordStatus | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> WordPage:
    return service.list_words(db, search=search, tag=tag, status=status, limit=limit, offset=offset)


@router.get("/wrong", response_model=list[WordOut])
def wrong_words(db: Session = Depends(get_db)) -> list[WordOut]:
    return service.wrong_words(db)


@router.get("/stats", response_model=VocabStats)
def stats(db: Session = Depends(get_db)) -> VocabStats:
    return service.stats(db)


@router.post("/import", response_model=ImportResult)
async def import_words(
    file: UploadFile = File(...), source: str | None = Form(None), db: Session = Depends(get_db)
) -> ImportResult:
    """匯入 CSV／Excel 單字表。"""
    try:
        return service.import_file(db, file.filename or "upload.csv", await file.read(), source)
    except ImportFormatError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/builtin", response_model=list[BuiltinList])
def builtin_lists() -> list[BuiltinList]:
    return service.list_builtin()


@router.post("/builtin/{name}/import", response_model=ImportResult)
def import_builtin(name: str, db: Session = Depends(get_db)) -> ImportResult:
    try:
        return service.import_builtin(db, name)
    except service.VocabError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
