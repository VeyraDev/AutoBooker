export type FormulaEditMode = "insert-inline" | "insert-block" | "edit";

export type FormulaEditRequest = {
  mode: FormulaEditMode;
  latex: string;
  pos?: number;
  nodeType?: "mathInline" | "mathBlock";
  numbered?: boolean;
  equationNumber?: string;
  label?: string;
};

type Handler = (req: FormulaEditRequest) => void;

let handler: Handler | null = null;

export function registerFormulaEditHandler(next: Handler | null): void {
  handler = next;
}

export function requestFormulaEdit(req: FormulaEditRequest): void {
  handler?.(req);
}
