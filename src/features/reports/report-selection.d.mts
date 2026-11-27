export type ReportSelection = { patientId: string; caseId: string; imageId: string; runId: string }
export declare function readReportSelection(storage: Pick<Storage, 'getItem'>, key: string): ReportSelection
export declare function validateReportBaseSelection(selection: ReportSelection, patients: Array<{ id: string }>, cases: Array<{ id: string; patient_id: string }>): ReportSelection
export declare function validateReportCaseSelection(selection: ReportSelection, images: Array<{ id: string; case_id: string }>, runs: Array<{ id: string; case_id: string; image_id: string | null }>): ReportSelection
export declare function saveReportSelection(storage: Pick<Storage, 'setItem' | 'removeItem'>, key: string, selection: ReportSelection): void
export declare function readSessionReportSelection(key: string): ReportSelection
export declare function saveSessionReportSelection(key: string, selection: ReportSelection): void
