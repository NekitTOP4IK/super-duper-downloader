import type { Preset, Sizes } from "../api/client";
import { formatBytes } from "../lib/format";

interface Props {
  options: Preset[];
  value: Preset;
  onChange: (preset: Preset) => void;
  label?: string;
  sizes?: Sizes;
}

export function Presets({ options, value, onChange, label, sizes }: Props) {
  return (
    <div className="presets" role="group" aria-label={label}>
      {options.map((preset) => {
        const size = sizes?.[preset];
        return (
          <button
            key={preset}
            type="button"
            className="chip"
            aria-pressed={preset === value}
            onClick={() => onChange(preset)}
          >
            {preset}
            {size ? <> <small>~{formatBytes(size)}</small></> : null}
          </button>
        );
      })}
    </div>
  );
}
