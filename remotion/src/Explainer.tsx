import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type ExplainerScene = {
  sceneNumber: number;
  narration: string;
  visualDescription: string;
  audioFile: string;
  durationInFrames: number;
  from: number;
};

export type ExplainerProps = {
  topic: string;
  fps: number;
  width: number;
  height: number;
  scenes: ExplainerScene[];
};

const C = {
  bg: "#0B1220",
  panel: "#17233A",
  teal: "#4FD1C5",
  gold: "#F2B84B",
  red: "#E87979",
  white: "#F4F6FA",
  muted: "#A6B0C2",
  purple: "#A78BFA",
};

const Visual: React.FC<{ scene: ExplainerScene }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entrance = spring({ frame, fps, config: { damping: 16 } });
  const float = Math.sin(frame / 13) * 12;
  const pulse = 1 + Math.sin(frame / 9) * 0.07;
  const reveal = (delay: number) =>
    spring({ frame: frame - delay, fps, config: { damping: 15 } });

  const text = scene.narration.toLowerCase();
  const n = scene.sceneNumber;

  // 1. Introduce the idea: a threat and a protective immune cell.
  if (n === 1) {
    return (
      <svg viewBox="0 0 1000 430" width="100%" height="100%">
        <defs>
          <radialGradient id="introGlow">
            <stop offset="0%" stopColor={C.teal} stopOpacity=".32" />
            <stop offset="100%" stopColor={C.teal} stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle cx="500" cy="210" r="190" fill="url(#introGlow)" />
        <g transform={`translate(310 ${210 + float}) scale(${pulse})`}>
          <circle r="105" fill="#123442" stroke={C.teal} strokeWidth="4" />
          <circle r="68" fill={C.teal} fillOpacity=".12" stroke={C.teal} strokeOpacity=".6" strokeWidth="2" />
          {Array.from({ length: 9 }, (_, i) => (
            <circle
              key={i}
              cx={Math.cos(i * Math.PI * 2 / 9) * 75}
              cy={Math.sin(i * Math.PI * 2 / 9) * 75}
              r="7"
              fill={C.teal}
            />
          ))}
        </g>
        <g transform={`translate(${690 - entrance * 80} ${205 - float}) rotate(${frame * 0.5})`}>
          {Array.from({ length: 12 }, (_, i) => (
            <path
              key={i}
              d="M0 -40 L0 -64"
              transform={`rotate(${i * 30})`}
              stroke={C.red}
              strokeWidth="8"
              strokeLinecap="round"
            />
          ))}
          <circle r="43" fill="#743B50" stroke={C.red} strokeWidth="3" />
          <circle cx="-12" cy="-9" r="8" fill="#F7B7B7" />
          <circle cx="15" cy="13" r="7" fill="#F7B7B7" />
          <circle cx="14" cy="-17" r="5" fill="#F7B7B7" />
        </g>
        <path d="M430 210 C470 160 520 260 570 210" fill="none" stroke={C.gold} strokeWidth="4" strokeDasharray="8 12" />
        <circle cx={450 + ((frame * 2) % 100)} cy={210 + Math.sin(frame / 7) * 22} r="8" fill={C.gold} />
        <text x="310" y="365" textAnchor="middle" fill={C.teal} fontSize="21" letterSpacing="3">IMMUNE DEFENSE</text>
        <text x="690" y="365" textAnchor="middle" fill={C.red} fontSize="21" letterSpacing="3">POTENTIAL THREAT</text>
      </svg>
    );
  }

  // 2. Vaccine delivery: a syringe introduces vaccine material.
  if (n === 2) {
    return (
      <svg viewBox="0 0 1000 430" width="100%" height="100%">
        <circle cx="500" cy="230" r="160" fill="#123442" fillOpacity=".45" />
        <g transform={`translate(${390 + float} 205) rotate(-28)`}>
          <rect x="-30" y="-130" width="60" height="180" rx="12" fill="#DDE7F1" fillOpacity=".15" stroke={C.teal} strokeWidth="4" />
          <rect x="-23" y="-40" width="46" height="80" rx="5" fill={C.teal} fillOpacity=".55" />
          <path d="M0 50 V125" stroke={C.white} strokeWidth="5" />
          <path d="M-14 -145 H14 M0 -145 V-130 M-42 -115 H42" stroke={C.white} strokeWidth="5" strokeLinecap="round" />
        </g>
        <path d="M460 180 C530 130 570 280 640 220" fill="none" stroke={C.teal} strokeWidth="4" strokeDasharray="8 12" />
        {Array.from({ length: 7 }, (_, i) => {
          const t = ((frame / 90 + i / 7) % 1);
          return <circle key={i} cx={465 + t * 180} cy={190 + Math.sin(t * Math.PI * 2 + i) * 30} r={5 + (i % 3)} fill={i % 2 ? C.gold : C.teal} opacity=".9" />;
        })}
        <g transform={`translate(730 ${235 + float})`}>
          <circle r="83" fill="#123442" stroke={C.teal} strokeWidth="4" />
          <circle r="48" fill={C.teal} fillOpacity=".14" />
          {Array.from({ length: 8 }, (_, i) => (
            <circle key={i} cx={Math.cos(i * Math.PI / 4) * 56} cy={Math.sin(i * Math.PI / 4) * 56} r="8" fill={C.gold} />
          ))}
        </g>
        <text x="390" y="365" fill={C.white} fontSize="20" textAnchor="middle">VACCINE</text>
        <text x="730" y="365" fill={C.teal} fontSize="20" textAnchor="middle">BODY'S CELLS</text>
      </svg>
    );
  }

  // 3. Show the range of vaccine antigens and pathogen-like structures.
  if (n === 3) {
    return (
      <svg viewBox="0 0 1000 430" width="100%" height="100%">
        <g transform={`translate(330 ${205 + float}) rotate(${frame * .3})`}>
          {Array.from({ length: 16 }, (_, i) => (
            <g key={i} transform={`rotate(${i * 22.5})`}>
              <path d="M0 -65 V-94" stroke={C.red} strokeWidth="8" strokeLinecap="round" />
              <circle cx="0" cy="-98" r="9" fill={C.gold} />
            </g>
          ))}
          <circle r="65" fill="#743B50" stroke={C.red} strokeWidth="4" />
          {Array.from({ length: 8 }, (_, i) => (
            <circle key={i} cx={Math.cos(i * Math.PI / 4) * 33} cy={Math.sin(i * Math.PI / 4) * 33} r="7" fill="#F7B7B7" />
          ))}
        </g>
        <path d="M445 205 H560" stroke={C.muted} strokeWidth="3" strokeDasharray="7 9" />
        <g transform={`translate(700 ${205 - float})`}>
          <circle r="83" fill="#15313A" stroke={C.teal} strokeWidth="3" />
          <circle r="61" fill={C.teal} fillOpacity=".12" />
          {Array.from({ length: 5 }, (_, i) => (
            <g key={i} transform={`rotate(${i * 72})`}>
              <rect x="-10" y="-89" width="20" height="32" rx="8" fill={C.gold} />
            </g>
          ))}
          <circle r="22" fill={C.teal} fillOpacity=".6" />
        </g>
        <text x="330" y="350" fill={C.red} fontSize="20" textAnchor="middle">MICROBE-LIKE SHAPE</text>
        <text x="700" y="350" fill={C.teal} fontSize="20" textAnchor="middle">SURFACE PROTEIN</text>
        <text x="500" y="395" fill={C.muted} fontSize="16" textAnchor="middle">Different vaccines can present different antigens</text>
      </svg>
    );
  }

  // 4. Recognition: an antigen meets a matching receptor.
  if (n === 4) {
    return (
      <svg viewBox="0 0 1000 430" width="100%" height="100%">
        <g transform={`translate(275 ${215 + float})`}>
          <circle r="110" fill="#123442" stroke={C.teal} strokeWidth="4" />
          <circle r="75" fill={C.teal} fillOpacity=".1" stroke={C.teal} strokeOpacity=".5" strokeWidth="2" />
          <path d="M-8 -100 L-8 -65 L-25 -48 M-8 -65 L10 -48" stroke={C.gold} strokeWidth="10" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M40 -94 L40 -62 L22 -44 M40 -62 L58 -44" stroke={C.teal} strokeWidth="8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="-25" cy="5" r="12" fill={C.teal} />
          <circle cx="28" cy="24" r="9" fill={C.gold} />
        </g>
        <path d={`M390 215 C470 ${130 + float} 530 ${300 - float} 610 215`} fill="none" stroke={C.gold} strokeWidth="4" strokeDasharray="7 10" />
        <circle cx={405 + ((frame * 2) % 180)} cy={215 + Math.sin(frame / 8) * 20} r="10" fill={C.gold} />
        <g transform={`translate(720 ${215 - float}) scale(${pulse})`}>
          <circle r="72" fill="#743B50" stroke={C.red} strokeWidth="4" />
          {Array.from({ length: 10 }, (_, i) => (
            <path key={i} d="M0 -72 V-96" transform={`rotate(${i * 36})`} stroke={C.red} strokeWidth="7" strokeLinecap="round" />
          ))}
          <circle r="29" fill={C.red} fillOpacity=".3" />
        </g>
        <text x="275" y="365" fill={C.teal} fontSize="20" textAnchor="middle">IMMUNE RECEPTOR</text>
        <text x="720" y="365" fill={C.red} fontSize="20" textAnchor="middle">ANTIGEN SIGNAL</text>
      </svg>
    );
  }

  // 5. Future protection: memory cells remain while a threat is recognized.
  if (n === 5) {
    return (
      <svg viewBox="0 0 1000 430" width="100%" height="100%">
        <g transform={`translate(280 ${210 + float})`}>
          <circle r="86" fill="#123442" stroke={C.teal} strokeWidth="4" />
          <circle r="51" fill={C.teal} fillOpacity=".2" />
          <circle cx="-15" cy="-8" r="12" fill={C.teal} />
          <circle cx="18" cy="15" r="10" fill={C.gold} />
          <circle cx="19" cy="-23" r="7" fill={C.teal} />
        </g>
        <g transform={`translate(500 ${210 - float})`}>
          <circle r="86" fill="#123442" stroke={C.teal} strokeWidth="4" />
          <circle r="51" fill={C.teal} fillOpacity=".2" />
          <circle cx="-15" cy="-8" r="12" fill={C.teal} />
          <circle cx="18" cy="15" r="10" fill={C.gold} />
          <circle cx="19" cy="-23" r="7" fill={C.teal} />
        </g>
        <path d="M385 210 H395 M605 210 H655" stroke={C.gold} strokeWidth="4" strokeDasharray="7 9" />
        <g transform={`translate(760 ${210 + Math.sin(frame / 10) * 10}) rotate(${frame * .5})`}>
          {Array.from({ length: 10 }, (_, i) => <path key={i} d="M0 -38 V-57" transform={`rotate(${i * 36})`} stroke={C.red} strokeWidth="6" strokeLinecap="round" />)}
          <circle r="38" fill="#743B50" stroke={C.red} strokeWidth="3" />
        </g>
        <path d="M650 130 L685 145 L675 180" fill="none" stroke={C.gold} strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
        <text x="390" y="355" fill={C.teal} fontSize="20" textAnchor="middle">IMMUNE MEMORY</text>
        <text x="760" y="355" fill={C.red} fontSize="20" textAnchor="middle">FUTURE EXPOSURE</text>
      </svg>
    );
  }

  // 6. mRNA: a strand provides instructions that a cell uses to make protein.
  if (n === 6 || text.includes("mrna") || text.includes("messenger rna")) {
    return (
      <svg viewBox="0 0 1000 430" width="100%" height="100%">
        <g transform={`translate(265 ${210 + float})`}>
          <circle r="105" fill="#123442" stroke={C.teal} strokeWidth="4" />
          <circle r="62" fill={C.teal} fillOpacity=".1" stroke={C.teal} strokeOpacity=".5" strokeWidth="2" />
          <path d={Array.from({ length: 11 }, (_, i) => `${i === 0 ? "M" : "L"}${-38 + i * 8} ${-38 + Math.sin(i * 1.3) * 25}`).join(" ")} fill="none" stroke={C.gold} strokeWidth="7" strokeLinecap="round" />
          <path d={Array.from({ length: 11 }, (_, i) => `${i === 0 ? "M" : "L"}${-38 + i * 8} ${8 + Math.sin(i * 1.3 + 1) * 25}`).join(" ")} fill="none" stroke={C.teal} strokeWidth="7" strokeLinecap="round" />
        </g>
        <path d="M385 210 C455 145 515 275 590 210" fill="none" stroke={C.gold} strokeWidth="4" strokeDasharray="8 10" />
        <circle cx={405 + ((frame * 2) % 170)} cy={210 + Math.sin(frame / 8) * 18} r="8" fill={C.gold} />
        <g transform={`translate(735 ${210 - float})`}>
          {Array.from({ length: 9 }, (_, i) => (
            <circle key={i} cx={Math.cos(i * Math.PI * 2 / 9) * 45} cy={Math.sin(i * Math.PI * 2 / 9) * 45} r={10 + (i % 3) * 3} fill={i % 2 ? C.teal : C.gold} opacity={reveal(i * 3)} />
          ))}
          <circle r="23" fill={C.purple} fillOpacity=".75" />
        </g>
        <text x="265" y="355" fill={C.gold} fontSize="20" textAnchor="middle">mRNA INSTRUCTIONS</text>
        <text x="735" y="355" fill={C.teal} fontSize="20" textAnchor="middle">PROTEIN PRODUCT</text>
      </svg>
    );
  }

  // 7. Conjugate vaccine: two components are joined.
  if (n === 7 || text.includes("conjugate") || text.includes("carrier antigen")) {
    return (
      <svg viewBox="0 0 1000 430" width="100%" height="100%">
        <g transform={`translate(285 ${205 + float}) scale(${pulse})`}>
          <circle r="58" fill="#743B50" stroke={C.red} strokeWidth="4" />
          {Array.from({ length: 8 }, (_, i) => <circle key={i} cx={Math.cos(i * Math.PI / 4) * 32} cy={Math.sin(i * Math.PI / 4) * 32} r="7" fill="#F7B7B7" />)}
        </g>
        <path d="M365 205 H425" stroke={C.gold} strokeWidth="5" strokeDasharray="7 8" />
        <circle cx="455" cy="205" r="25" fill={C.gold} />
        <path d="M485 205 H545" stroke={C.gold} strokeWidth="5" strokeDasharray="7 8" />
        <g transform={`translate(670 ${205 - float}) scale(${pulse})`}>
          <circle r="91" fill="#123442" stroke={C.teal} strokeWidth="4" />
          {Array.from({ length: 12 }, (_, i) => <circle key={i} cx={Math.cos(i * Math.PI / 6) * 57} cy={Math.sin(i * Math.PI / 6) * 57} r="8" fill={C.teal} />)}
          <circle r="36" fill={C.teal} fillOpacity=".2" />
          <circle cx="-12" cy="-10" r="10" fill={C.gold} />
          <circle cx="17" cy="12" r="9" fill={C.gold} />
        </g>
        <text x="285" y="350" fill={C.red} fontSize="20" textAnchor="middle">WEAKER ANTIGEN</text>
        <text x="455" y="350" fill={C.gold} fontSize="18" textAnchor="middle">JOINED</text>
        <text x="670" y="350" fill={C.teal} fontSize="20" textAnchor="middle">CARRIER ANTIGEN</text>
      </svg>
    );
  }

  // 8. Summary: protective response surrounding a recognized pathogen.
  return (
    <svg viewBox="0 0 1000 430" width="100%" height="100%">
      <circle cx="500" cy="210" r={130 * pulse} fill={C.teal} fillOpacity=".06" stroke={C.teal} strokeOpacity=".4" strokeWidth="3" />
      <circle cx="500" cy="210" r="90" fill="none" stroke={C.gold} strokeWidth="3" strokeDasharray="9 12" transform={`rotate(${frame * 0.6} 500 210)`} />
      <g transform={`translate(500 ${210 + float}) rotate(${frame * .4})`}>
        {Array.from({ length: 12 }, (_, i) => <path key={i} d="M0 -42 V-60" transform={`rotate(${i * 30})`} stroke={C.red} strokeWidth="7" strokeLinecap="round" />)}
        <circle r="42" fill="#743B50" stroke={C.red} strokeWidth="3" />
        <circle cx="-13" cy="-9" r="7" fill="#F7B7B7" />
        <circle cx="14" cy="12" r="7" fill="#F7B7B7" />
      </g>
      {Array.from({ length: 6 }, (_, i) => {
        const angle = i * Math.PI / 3 + frame / 70;
        const x = 500 + Math.cos(angle) * 155;
        const y = 210 + Math.sin(angle) * 125;
        return (
          <g key={i} transform={`translate(${x} ${y}) rotate(${angle * 180 / Math.PI + 90})`}>
            <path d="M0 20 V0 M0 0 L-13 -15 M0 0 L13 -15" stroke={C.teal} strokeWidth="7" fill="none" strokeLinecap="round" />
          </g>
        );
      })}
      <text x="500" y="390" fill={C.teal} fontSize="21" textAnchor="middle" letterSpacing="3">RECOGNITION · RESPONSE · MEMORY</text>
    </svg>
  );
};

const Scene: React.FC<{ scene: ExplainerScene; topic: string }> = ({ scene, topic }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const entrance = spring({ frame, fps, config: { damping: 18, stiffness: 90 } });
  const fade = interpolate(
    frame,
    [0, 8, scene.durationInFrames - 8, scene.durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const titles = [
    "Meet the immune system",
    "Introducing a vaccine",
    "Recognizing an antigen",
    "The immune response begins",
    "Preparing for the future",
    "From mRNA to protein",
    "Combining antigens",
    "Building immune memory",
  ];
  const title = titles[scene.sceneNumber - 1] || `The key idea — ${scene.sceneNumber}`;

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 45%, #172943 0%, ${C.bg} 72%)`,
        color: C.white,
        fontFamily: "Arial, Helvetica, sans-serif",
        opacity: fade,
        overflow: "hidden",
      }}
    >
      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 6,
        background: `linear-gradient(90deg, ${C.teal}, ${C.gold}, ${C.red})`,
        transformOrigin: "left",
        transform: `scaleX(${Math.min(1, (frame + 1) / scene.durationInFrames)})`,
      }} />

      <div style={{
        position: "absolute", top: 35, left: 64, right: 64,
        display: "flex", justifyContent: "space-between",
        fontSize: 15, color: C.muted, letterSpacing: 3,
      }}>
        <span>FIELD NOTES / EXPLAINED</span>
        <span>{String(scene.sceneNumber).padStart(2, "0")} / {String(8).padStart(2, "0")}</span>
      </div>

      <div style={{
        position: "absolute", top: 82, left: 72, right: 72,
        textAlign: "center",
        transform: `translateY(${interpolate(entrance, [0, 1], [18, 0])}px)`,
        opacity: entrance,
      }}>
        <div style={{
          color: C.teal, fontSize: 14, letterSpacing: 5,
          textTransform: "uppercase", marginBottom: 10,
        }}>{topic}</div>
        <div style={{
          fontSize: 39, lineHeight: 1.15, fontWeight: 700,
          letterSpacing: -0.7,
        }}>{title}</div>
      </div>

      <div style={{
        position: "absolute", top: 165, left: 95, right: 95, height: 355,
        transform: `scale(${interpolate(entrance, [0, 1], [0.94, 1])})`,
        transformOrigin: "center",
      }}>
        <Visual scene={scene} />
      </div>

      <div style={{
        position: "absolute", left: 100, right: 100, bottom: 38,
        minHeight: 105, boxSizing: "border-box",
        padding: "20px 30px", borderRadius: 16,
        border: `1px solid #33445C`,
        borderLeft: `5px solid ${C.teal}`,
        background: "rgba(18, 27, 46, .94)",
        display: "flex", alignItems: "center", justifyContent: "center",
        textAlign: "center",
        transform: `translateY(${interpolate(entrance, [0, 1], [15, 0])}px)`,
        opacity: entrance,
      }}>
        <div style={{ fontSize: 22, lineHeight: 1.4, fontWeight: 500 }}>
          {scene.narration}
        </div>
      </div>

      <Audio src={staticFile(scene.audioFile)} />
    </AbsoluteFill>
  );
};

export const Explainer: React.FC<ExplainerProps> = ({ topic, scenes }) => (
  <AbsoluteFill style={{ backgroundColor: C.bg }}>
    {scenes.map((scene) => (
      <Sequence
        key={scene.sceneNumber}
        from={scene.from}
        durationInFrames={scene.durationInFrames}
        name={`Scene ${scene.sceneNumber}`}
      >
        <Scene scene={scene} topic={topic} />
      </Sequence>
    ))}
  </AbsoluteFill>
);
