import { SECURITY } from "../content";
import { Eyebrow, H2, Section } from "./Section";

export function Trust() {
  return (
    <Section id="trust" state="success" anchor="left" label="Security" className="py-28 md:py-40">
      <div className="md:ml-auto md:w-[54%]">
        <Eyebrow tone="earth">Security, enforced in code</Eyebrow>
        <H2>Trust you can verify, not a promise in a prompt.</H2>
        <p data-reveal className="mt-6 text-lg text-ink/70">
          The language model never gets raw shell or open OS access. It can only request one of a fixed set of reviewed
          tools, each with a declared risk level — and the executor, not the model, decides when to ask you.
        </p>
        <ol className="mt-10 space-y-3">
          {SECURITY.map((s, i) => (
            <li key={s.title} data-reveal className="glass p-5 md:p-6 flex gap-5">
              <span className="font-mono text-sm text-earth pt-0.5">0{i + 1}</span>
              <div>
                <h3 className="text-lg font-semibold">{s.title}</h3>
                <p className="mt-1.5 text-[15px] leading-relaxed text-ink/65">{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </Section>
  );
}
