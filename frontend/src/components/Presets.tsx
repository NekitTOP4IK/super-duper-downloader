import type { Preset } from "../api/client";

interface Props {
  options: Preset[];
  value: Preset;
  onChange: (preset: Preset) => void;
  label?: string;
}

export function Presets({ options, value, onChange, label }: Props) {
  return (
    <div className="presets" role="group" aria-label={label}>
      {options.map((preset) => (
        <button
          key={preset}
          type="button"
          className="chip"
          aria-pressed={preset === value}
          onClick={() => onChange(preset)}
        >
          {preset}
        </button>
      ))}
    </div>
  );
}
