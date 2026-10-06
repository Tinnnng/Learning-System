/** 後端 API 的資料型別（由 npm run gen:api 從 OpenAPI 產生，不要手改 api-types.ts）。 */

import type { components } from './api-types'

type Schemas = components['schemas']

export type PaperSummary = Schemas['PaperSummary']
export type PaperDetail = Schemas['PaperDetail']
export type PaperRef = Schemas['PaperRef']
export type QuestionOut = Schemas['QuestionOut']
export type QuestionWithPaper = Schemas['QuestionWithPaper']
export type QuestionFilter = Schemas['QuestionFilter']
export type FilterOptions = Schemas['FilterOptions']
export type Asset = Schemas['Asset']

export type SessionCreate = Schemas['SessionCreate']
export type SessionOut = Schemas['SessionOut']
export type SessionSummary = Schemas['SessionSummary']
export type ItemOut = Schemas['ItemOut']

export type WrongQuestionOut = Schemas['WrongQuestionOut']
export type Overview = Schemas['Overview']
export type ProgressOut = Schemas['ProgressOut']

export type DailyQuiz = Schemas['DailyQuiz']
export type QuizItem = Schemas['QuizItem']
export type VocabAnswerResult = Schemas['AnswerResult']
export type VocabStats = Schemas['VocabStats']
export type WordOut = Schemas['WordOut']
export type WordPage = Schemas['WordPage']
export type ImportResult = Schemas['ImportResult']
export type BuiltinList = Schemas['BuiltinList']

export type ConvertedFile = Schemas['ConvertedFile']
export type ImportBundle = Schemas['ImportBundle']
export type ImportOutcome = Schemas['ImportOutcome']

export type DueSummary = Schemas['DueSummary']
