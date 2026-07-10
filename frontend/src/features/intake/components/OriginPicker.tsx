import type { CreationOrigin } from "@/features/intake/api/intakeApi";
import { ORIGIN_LABELS } from "@/features/intake/hooks/useIntakeFlow";

type Props = {
  onSelect: (origin: CreationOrigin) => void;
};

export default function OriginPicker({ onSelect }: Props) {
  return (
    <div className="grid gap-2">
      {(Object.keys(ORIGIN_LABELS) as CreationOrigin[]).map((key) => (
        <button
          key={key}
          type="button"
          className="rounded-lg border border-slate-200 px-4 py-3 text-left text-sm hover:border-brand hover:bg-brand/5"
          onClick={() => onSelect(key)}
        >
          {ORIGIN_LABELS[key]}
        </button>
      ))}
    </div>
  );
}
