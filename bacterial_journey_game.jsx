import { useState, useEffect, useRef } from "react";

const STAGES = [
  {
    id: 0,
    phase: "入侵",
    title: "第一站：病原体登场",
    lens: "医学微生物学",
    lensIcon: "🔬",
    lensColor: "#6ee7b7",
    narrative:
      "一颗肺炎链球菌（Streptococcus pneumoniae）随着飞沫被吸入鼻腔。它是革兰阳性菌，表面包裹着一层厚厚的荚膜——这是它最重要的「隐身斗篷」。",
    question: "肺炎链球菌荚膜的主要致病作用是什么？",
    options: [
      { text: "产生外毒素，直接破坏宿主细胞", correct: false },
      { text: "抗吞噬，帮助细菌逃避免疫细胞的清除", correct: true },
      { text: "帮助细菌在体外环境中长期存活", correct: false },
      { text: "促进细菌穿透血脑屏障", correct: false },
    ],
    explanation:
      "荚膜是肺炎链球菌最重要的毒力因子，其主要作用是抗吞噬——阻止中性粒细胞和巨噬细胞的吞噬杀伤。这也是为什么荚膜多糖是制备疫苗的关键抗原成分。",
    aha: "🎯 啊哈时刻：荚膜既是致病的关键，也是疫苗设计的靶点——攻防一体！",
  },
  {
    id: 1,
    phase: "入侵",
    title: "第二站：突破防线",
    lens: "局部解剖学",
    lensIcon: "🗺️",
    lensColor: "#93c5fd",
    narrative:
      "细菌随气流经鼻腔→咽→喉→气管→支气管，一路深入。我们来换一副「解剖学眼镜」看看这条路径。气管在第4-5胸椎水平分为左、右主支气管，右主支气管较左侧更粗、更短、更陡直。",
    question: "异物或病原体吸入后，更容易落入哪一侧？为什么？",
    options: [
      { text: "左侧，因为左主支气管更长", correct: false },
      { text: "右侧，因为右主支气管更粗、短、陡直", correct: true },
      { text: "两侧概率相同，取决于体位", correct: false },
      { text: "左侧，因为左肺更大", correct: false },
    ],
    explanation:
      "右主支气管较粗、较短、与气管纵轴的延续方向较一致（更陡直），所以经气管坠入的异物或吸入的病原体更容易进入右侧。这也是右肺感染和吸入性肺炎更常见的解剖学基础。",
    aha: "🎯 啊哈时刻：为什么吸入性肺炎好发右下肺？解剖结构决定了感染的「地理偏好」！",
  },
  {
    id: 2,
    phase: "定植",
    title: "第三站：抵达肺泡",
    lens: "组织学与胚胎学",
    lensIcon: "🧫",
    lensColor: "#c4b5fd",
    narrative:
      "细菌终于到达了呼吸的最前线——肺泡。我们换上「组织学眼镜」，看看微观世界的肺泡长什么样。肺泡壁由两种上皮细胞构成，中间是丰富的毛细血管网。",
    question: "Ⅰ型肺泡细胞和Ⅱ型肺泡细胞，哪个负责气体交换，哪个分泌肺表面活性物质？",
    options: [
      { text: "Ⅰ型负责气体交换，Ⅱ型分泌肺表面活性物质", correct: true },
      { text: "Ⅱ型负责气体交换，Ⅰ型分泌肺表面活性物质", correct: false },
      { text: "两型都参与气体交换，仅Ⅰ型分泌活性物质", correct: false },
      { text: "两型功能完全相同，只是形态不同", correct: false },
    ],
    explanation:
      "Ⅰ型肺泡细胞扁平，覆盖肺泡约95%的表面积，与毛细血管内皮共同构成气-血屏障，是气体交换的结构基础。Ⅱ型肺泡细胞体积较大呈立方形，分泌肺表面活性物质（主要成分为二棕榈酰卵磷脂），降低肺泡表面张力，防止肺泡塌陷。",
    aha: "🎯 啊哈时刻：Ⅰ型管「换气」，Ⅱ型管「撑开」——两型分工，缺一不可！",
  },
  {
    id: 3,
    phase: "战斗",
    title: "第四站：免疫反击战",
    lens: "病理学",
    lensIcon: "🔴",
    lensColor: "#fca5a5",
    narrative:
      "细菌在肺泡内大量繁殖，触发了剧烈的炎症反应。我们换上「病理学眼镜」来看看大叶性肺炎的经典四期病变。这是一场从充血到消散的完整战役。",
    question: "大叶性肺炎的红色肝样变期，肺泡腔内主要充满了什么？",
    options: [
      { text: "大量浆液性渗出液", correct: false },
      { text: "纤维素和大量红细胞", correct: true },
      { text: "纤维素和大量中性粒细胞", correct: false },
      { text: "坏死的肺组织碎片", correct: false },
    ],
    explanation:
      "红色肝样变期（实变早期），肺泡腔内充满纤维素和大量红细胞，使肺组织呈暗红色、质地变实，切面似肝脏，故名。而灰色肝样变期则以纤维素和大量中性粒细胞为主，红细胞被降解，故肺组织转为灰白色。",
    aha: "🎯 啊哈时刻：红色→灰色的转变，本质是红细胞被降解、白细胞接管战场的过程！",
  },
  {
    id: 4,
    phase: "战斗",
    title: "第五站：功能告急",
    lens: "生理学",
    lensIcon: "⚡",
    lensColor: "#fcd34d",
    narrative:
      "肺泡被渗出物填满，气体交换受阻。我们换上「生理学眼镜」看看正常的气体交换是怎么工作的——又是在哪个环节被破坏的。",
    question: "炎症渗出物充满肺泡时，通气/血流比值（V/Q）会发生什么变化？",
    options: [
      { text: "V/Q 升高，产生死腔样效应", correct: false },
      { text: "V/Q 降低，产生功能性分流", correct: true },
      { text: "V/Q 不变，仅弥散功能障碍", correct: false },
      { text: "V/Q 完全为零，血流停止", correct: false },
    ],
    explanation:
      "实变区域的肺泡通气量（V）大幅减少甚至为零，但血流（Q）仍在灌注，导致V/Q比值显著降低，产生「功能性动-静脉分流」——静脉血流经这些区域却未被充分氧合，导致低氧血症。这就是肺炎患者缺氧的核心生理学机制。",
    aha: "🎯 啊哈时刻：不是「没吸够气」，而是「吸进的气到不了血里」——V/Q失配才是缺氧的关键！",
  },
  {
    id: 5,
    phase: "危机",
    title: "第六站：全身风暴",
    lens: "病理生理学",
    lensIcon: "🌊",
    lensColor: "#f9a8d4",
    narrative:
      "感染不仅仅是肺的事。细菌和炎症介质入血，可能引发全身炎症反应综合征（SIRS），严重时导致感染性休克。我们换上「病理生理学眼镜」看看休克的微循环变化。",
    question: "感染性休克早期（暖休克/高动力型），微循环的特征性变化是什么？",
    options: [
      { text: "微动脉和微静脉同时收缩", correct: false },
      { text: "微血管扩张，外周阻力降低", correct: true },
      { text: "微循环淤滞，血流停止", correct: false },
      { text: "动-静脉短路关闭", correct: false },
    ],
    explanation:
      "感染性休克（特别是革兰阳性菌引起的）早期常表现为高动力型/暖休克：内毒素和大量炎症介质（如TNF-α、NO等）导致微血管广泛扩张，外周阻力降低，心输出量代偿性增加，皮肤温暖。但有效循环血量不足，组织灌注仍不充分。",
    aha: "🎯 啊哈时刻：皮肤发暖≠病情好转——暖休克的「暖」是微血管失控扩张的假象！",
  },
  {
    id: 6,
    phase: "诊治",
    title: "第七站：临床救治",
    lens: "传染病学",
    lensIcon: "💊",
    lensColor: "#67e8f9",
    narrative:
      "患者被送入医院。我们最后换上「传染病学/临床眼镜」，看看从诊断到治疗的决策过程。医生需要尽快确定病原体、选择抗菌方案。",
    question: "社区获得性肺炎（CAP）经验性抗菌治疗，以下哪个原则最重要？",
    options: [
      { text: "必须等到病原学结果出来再用药", correct: false },
      { text: "直接使用最广谱的抗生素", correct: false },
      { text: "尽早经验性用药，同时送检标本，后续根据结果调整", correct: true },
      { text: "仅对症治疗，不使用抗生素", correct: false },
    ],
    explanation:
      "CAP的治疗强调「尽早、足量」的经验性抗菌治疗——在留取痰液、血液等标本后立即给药，不等结果。后续根据病原学检查和药敏结果进行「降阶梯」调整。每延迟1小时用药，病死率可能增加。这体现了「先打后看」的临床决策逻辑。",
    aha: "🎯 啊哈时刻：临床不等「标准答案」——先救命，再精准！这就是经验性治疗的智慧。",
  },
];

const PHASE_MAP = {
  入侵: { emoji: "🦠", color: "#6ee7b7" },
  定植: { emoji: "🫁", color: "#c4b5fd" },
  战斗: { emoji: "⚔️", color: "#fca5a5" },
  危机: { emoji: "🚨", color: "#f9a8d4" },
  诊治: { emoji: "💉", color: "#67e8f9" },
};

function FloatingParticles() {
  return (
    <div style={{ position: "fixed", inset: 0, pointerEvents: "none", overflow: "hidden", zIndex: 0 }}>
      {Array.from({ length: 20 }).map((_, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            width: `${3 + Math.random() * 6}px`,
            height: `${3 + Math.random() * 6}px`,
            borderRadius: "50%",
            background: `rgba(${100 + Math.random() * 155}, ${100 + Math.random() * 155}, ${200 + Math.random() * 55}, ${0.15 + Math.random() * 0.15})`,
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
            animation: `float-particle ${8 + Math.random() * 12}s ease-in-out infinite`,
            animationDelay: `${-Math.random() * 10}s`,
          }}
        />
      ))}
      <style>{`
        @keyframes float-particle {
          0%, 100% { transform: translate(0, 0) scale(1); opacity: 0.3; }
          25% { transform: translate(${30}px, -${40}px) scale(1.3); opacity: 0.5; }
          50% { transform: translate(-${20}px, ${30}px) scale(0.8); opacity: 0.2; }
          75% { transform: translate(${40}px, ${20}px) scale(1.1); opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}

export default function BacterialJourneyGame() {
  const [screen, setScreen] = useState("welcome");
  const [currentStage, setCurrentStage] = useState(0);
  const [selected, setSelected] = useState(null);
  const [answered, setAnswered] = useState(false);
  const [score, setScore] = useState(0);
  const [streak, setStreak] = useState(0);
  const [maxStreak, setMaxStreak] = useState(0);
  const [results, setResults] = useState([]);
  const [showAha, setShowAha] = useState(false);
  const [fadeIn, setFadeIn] = useState(true);
  const scrollRef = useRef(null);

  useEffect(() => {
    setFadeIn(false);
    const t = setTimeout(() => setFadeIn(true), 50);
    return () => clearTimeout(t);
  }, [currentStage, screen]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [currentStage, screen, showAha]);

  const stage = STAGES[currentStage];
  const total = STAGES.length;

  function handleSelect(idx) {
    if (answered) return;
    setSelected(idx);
    setAnswered(true);
    const correct = stage.options[idx].correct;
    const newResults = [...results, { stageId: stage.id, correct, lens: stage.lens }];
    setResults(newResults);
    if (correct) {
      setScore((s) => s + 1);
      setStreak((s) => {
        const ns = s + 1;
        if (ns > maxStreak) setMaxStreak(ns);
        return ns;
      });
    } else {
      setStreak(0);
    }
  }

  function handleNext() {
    if (!showAha) {
      setShowAha(true);
      return;
    }
    setShowAha(false);
    setAnswered(false);
    setSelected(null);
    if (currentStage < total - 1) {
      setCurrentStage((c) => c + 1);
    } else {
      setScreen("summary");
    }
  }

  function restart() {
    setScreen("welcome");
    setCurrentStage(0);
    setSelected(null);
    setAnswered(false);
    setScore(0);
    setStreak(0);
    setMaxStreak(0);
    setResults([]);
    setShowAha(false);
  }

  const bg = "linear-gradient(160deg, #0a0e1a 0%, #121a2e 40%, #0d1520 100%)";

  return (
    <div
      style={{
        minHeight: "100vh",
        background: bg,
        color: "#e2e8f0",
        fontFamily: "'Noto Serif SC', 'Source Han Serif SC', Georgia, serif",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <FloatingParticles />
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700;900&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        @keyframes fade-up { from { opacity:0; transform:translateY(24px); } to { opacity:1; transform:translateY(0); } }
        @keyframes pulse-glow { 0%,100% { box-shadow: 0 0 20px rgba(110,231,183,0.15); } 50% { box-shadow: 0 0 40px rgba(110,231,183,0.3); } }
        @keyframes shake { 0%,100%{transform:translateX(0)} 25%{transform:translateX(-6px)} 75%{transform:translateX(6px)} }
        @keyframes aha-pop { from { opacity:0; transform:scale(0.9) translateY(12px); } to { opacity:1; transform:scale(1) translateY(0); } }
        .opt-btn { transition: all 0.25s ease; }
        .opt-btn:hover:not(.disabled) { transform: translateY(-2px); }
      `}</style>

      <div
        ref={scrollRef}
        style={{
          maxWidth: 680,
          margin: "0 auto",
          padding: "24px 20px 60px",
          position: "relative",
          zIndex: 1,
          minHeight: "100vh",
        }}
      >
        {/* ===== WELCOME ===== */}
        {screen === "welcome" && (
          <div
            style={{
              animation: "fade-up 0.6s ease",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              minHeight: "85vh",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: 64, marginBottom: 16 }}>🦠</div>
            <h1
              style={{
                fontSize: 28,
                fontWeight: 900,
                lineHeight: 1.4,
                marginBottom: 8,
                background: "linear-gradient(135deg, #6ee7b7, #93c5fd, #c4b5fd)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              细菌入侵之旅
            </h1>
            <p style={{ fontSize: 15, color: "#94a3b8", lineHeight: 1.7, marginBottom: 8, maxWidth: 480 }}>
              跟随一颗肺炎链球菌，从飞沫吸入到被免疫系统消灭
            </p>
            <p style={{ fontSize: 13, color: "#64748b", lineHeight: 1.8, marginBottom: 32, maxWidth: 440 }}>
              7 道关卡 · 7 副学科眼镜 · 跨越 7 本教材
              <br />
              每一关切换一个学科视角，串起完整的感染故事
            </p>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
                gap: 10,
                width: "100%",
                maxWidth: 440,
                marginBottom: 36,
              }}
            >
              {[
                { icon: "🔬", name: "微生物学" },
                { icon: "🗺️", name: "局部解剖" },
                { icon: "🧫", name: "组织胚胎" },
                { icon: "🔴", name: "病理学" },
                { icon: "⚡", name: "生理学" },
                { icon: "🌊", name: "病理生理" },
                { icon: "💊", name: "传染病学" },
              ].map((d) => (
                <div
                  key={d.name}
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    borderRadius: 10,
                    padding: "10px 8px",
                    fontSize: 12,
                    color: "#94a3b8",
                  }}
                >
                  <span style={{ fontSize: 20, display: "block", marginBottom: 4 }}>{d.icon}</span>
                  {d.name}
                </div>
              ))}
            </div>

            <button
              onClick={() => setScreen("game")}
              style={{
                background: "linear-gradient(135deg, #6ee7b7, #34d399)",
                color: "#0a0e1a",
                border: "none",
                borderRadius: 14,
                padding: "14px 48px",
                fontSize: 17,
                fontWeight: 700,
                cursor: "pointer",
                fontFamily: "inherit",
                animation: "pulse-glow 2.5s ease infinite",
              }}
            >
              开始旅程 →
            </button>
          </div>
        )}

        {/* ===== GAME ===== */}
        {screen === "game" && (
          <div
            style={{
              animation: fadeIn ? "fade-up 0.5s ease" : "none",
              opacity: fadeIn ? 1 : 0,
            }}
          >
            {/* Progress */}
            <div style={{ marginBottom: 24 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 10,
                  fontSize: 13,
                  color: "#64748b",
                }}
              >
                <span>
                  关卡 {currentStage + 1} / {total}
                </span>
                <span>
                  ✅ {score} · 🔥 连续 {streak}
                </span>
              </div>
              <div
                style={{
                  height: 4,
                  borderRadius: 2,
                  background: "rgba(255,255,255,0.08)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${((currentStage + (answered ? 1 : 0)) / total) * 100}%`,
                    background: "linear-gradient(90deg, #6ee7b7, #93c5fd)",
                    borderRadius: 2,
                    transition: "width 0.5s ease",
                  }}
                />
              </div>
              {/* Stage dots */}
              <div
                style={{
                  display: "flex",
                  gap: 4,
                  justifyContent: "center",
                  marginTop: 12,
                }}
              >
                {STAGES.map((s, i) => {
                  const done = i < currentStage || (i === currentStage && answered);
                  const active = i === currentStage;
                  const r = results[i];
                  return (
                    <div
                      key={i}
                      style={{
                        width: active ? 28 : 20,
                        height: 20,
                        borderRadius: 10,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 10,
                        transition: "all 0.3s ease",
                        background: done
                          ? r && r.correct
                            ? "rgba(110,231,183,0.3)"
                            : "rgba(252,165,165,0.3)"
                          : active
                          ? "rgba(255,255,255,0.15)"
                          : "rgba(255,255,255,0.06)",
                        border: active ? `1.5px solid ${s.lensColor}` : "1px solid transparent",
                      }}
                    >
                      {done ? (r && r.correct ? "✓" : "✗") : active ? s.lensIcon : ""}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Lens badge */}
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                background: `${stage.lensColor}15`,
                border: `1px solid ${stage.lensColor}40`,
                borderRadius: 20,
                padding: "6px 14px",
                marginBottom: 16,
                fontSize: 13,
              }}
            >
              <span>{stage.lensIcon}</span>
              <span style={{ color: stage.lensColor, fontWeight: 600 }}>
                换上眼镜 → {stage.lens}
              </span>
            </div>

            {/* Phase + Title */}
            <div style={{ marginBottom: 6 }}>
              <span
                style={{
                  fontSize: 12,
                  color: PHASE_MAP[stage.phase]?.color || "#94a3b8",
                  letterSpacing: 2,
                }}
              >
                {PHASE_MAP[stage.phase]?.emoji} {stage.phase}阶段
              </span>
            </div>
            <h2
              style={{
                fontSize: 22,
                fontWeight: 700,
                marginBottom: 16,
                color: "#f1f5f9",
              }}
            >
              {stage.title}
            </h2>

            {/* Narrative */}
            <div
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: 14,
                padding: "18px 20px",
                marginBottom: 24,
                fontSize: 15,
                lineHeight: 1.85,
                color: "#cbd5e1",
                borderLeft: `3px solid ${stage.lensColor}40`,
              }}
            >
              {stage.narrative}
            </div>

            {!showAha && (
              <>
                {/* Question */}
                <h3
                  style={{
                    fontSize: 16,
                    fontWeight: 600,
                    marginBottom: 16,
                    color: "#e2e8f0",
                    lineHeight: 1.6,
                  }}
                >
                  💡 {stage.question}
                </h3>

                {/* Options */}
                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 20 }}>
                  {stage.options.map((opt, idx) => {
                    const isSelected = selected === idx;
                    const isCorrect = opt.correct;
                    let bg2 = "rgba(255,255,255,0.04)";
                    let border2 = "1px solid rgba(255,255,255,0.1)";
                    let labelColor = "#94a3b8";
                    if (answered) {
                      if (isCorrect) {
                        bg2 = "rgba(110,231,183,0.12)";
                        border2 = "1px solid rgba(110,231,183,0.4)";
                        labelColor = "#6ee7b7";
                      } else if (isSelected && !isCorrect) {
                        bg2 = "rgba(252,165,165,0.12)";
                        border2 = "1px solid rgba(252,165,165,0.4)";
                        labelColor = "#fca5a5";
                      }
                    }
                    return (
                      <button
                        key={idx}
                        className={`opt-btn ${answered ? "disabled" : ""}`}
                        onClick={() => handleSelect(idx)}
                        style={{
                          background: bg2,
                          border: border2,
                          borderRadius: 12,
                          padding: "14px 16px",
                          textAlign: "left",
                          color: "#e2e8f0",
                          fontSize: 14,
                          lineHeight: 1.6,
                          cursor: answered ? "default" : "pointer",
                          fontFamily: "inherit",
                          display: "flex",
                          alignItems: "flex-start",
                          gap: 10,
                          animation:
                            answered && isSelected && !isCorrect ? "shake 0.3s ease" : "none",
                        }}
                      >
                        <span
                          style={{
                            minWidth: 24,
                            height: 24,
                            borderRadius: 12,
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: 12,
                            fontWeight: 700,
                            background: "rgba(255,255,255,0.08)",
                            color: labelColor,
                            flexShrink: 0,
                            marginTop: 1,
                          }}
                        >
                          {answered ? (isCorrect ? "✓" : isSelected ? "✗" : String.fromCharCode(65 + idx)) : String.fromCharCode(65 + idx)}
                        </span>
                        <span>{opt.text}</span>
                      </button>
                    );
                  })}
                </div>

                {/* Explanation */}
                {answered && (
                  <div
                    style={{
                      background: "rgba(255,255,255,0.03)",
                      border: "1px solid rgba(255,255,255,0.08)",
                      borderRadius: 14,
                      padding: "18px 20px",
                      marginBottom: 20,
                      animation: "fade-up 0.4s ease",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: selected !== null && stage.options[selected].correct ? "#6ee7b7" : "#fca5a5",
                        marginBottom: 8,
                      }}
                    >
                      {selected !== null && stage.options[selected].correct ? "✅ 回答正确！" : "❌ 答错了，没关系"}
                    </div>
                    <p style={{ fontSize: 14, lineHeight: 1.85, color: "#94a3b8" }}>
                      {stage.explanation}
                    </p>
                  </div>
                )}
              </>
            )}

            {/* Aha moment */}
            {showAha && (
              <div
                style={{
                  background: `linear-gradient(135deg, ${stage.lensColor}10, ${stage.lensColor}05)`,
                  border: `1px solid ${stage.lensColor}30`,
                  borderRadius: 16,
                  padding: "24px 20px",
                  marginBottom: 20,
                  textAlign: "center",
                  animation: "aha-pop 0.5s ease",
                }}
              >
                <div style={{ fontSize: 36, marginBottom: 12 }}>💡</div>
                <p
                  style={{
                    fontSize: 16,
                    lineHeight: 1.9,
                    color: "#e2e8f0",
                    fontWeight: 600,
                  }}
                >
                  {stage.aha}
                </p>
              </div>
            )}

            {/* Next button */}
            {answered && (
              <button
                onClick={handleNext}
                style={{
                  width: "100%",
                  background: showAha
                    ? "linear-gradient(135deg, #6ee7b7, #34d399)"
                    : "rgba(255,255,255,0.08)",
                  color: showAha ? "#0a0e1a" : "#e2e8f0",
                  border: showAha ? "none" : "1px solid rgba(255,255,255,0.15)",
                  borderRadius: 12,
                  padding: "14px",
                  fontSize: 15,
                  fontWeight: 600,
                  cursor: "pointer",
                  fontFamily: "inherit",
                  animation: "fade-up 0.3s ease",
                }}
              >
                {showAha
                  ? currentStage < total - 1
                    ? `前往第 ${currentStage + 2} 站 →`
                    : "查看旅程总结 →"
                  : "查看跨学科「啊哈时刻」 💡"}
              </button>
            )}
          </div>
        )}

        {/* ===== SUMMARY ===== */}
        {screen === "summary" && (
          <div style={{ animation: "fade-up 0.6s ease" }}>
            <div style={{ textAlign: "center", marginBottom: 32, paddingTop: 20 }}>
              <div style={{ fontSize: 56, marginBottom: 12 }}>
                {score === total ? "🏆" : score >= total * 0.7 ? "🎉" : "💪"}
              </div>
              <h2
                style={{
                  fontSize: 24,
                  fontWeight: 900,
                  marginBottom: 8,
                  background: "linear-gradient(135deg, #6ee7b7, #93c5fd)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                旅程完成！
              </h2>
              <p style={{ fontSize: 14, color: "#94a3b8" }}>
                你跟随肺炎链球菌走完了从入侵到被消灭的全程
              </p>
            </div>

            {/* Stats */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr 1fr",
                gap: 12,
                marginBottom: 28,
              }}
            >
              {[
                { label: "正确率", value: `${Math.round((score / total) * 100)}%`, sub: `${score}/${total}` },
                { label: "最长连续", value: `${maxStreak}`, sub: "🔥 streak" },
                { label: "学科覆盖", value: "7", sub: "门课打通" },
              ].map((s) => (
                <div
                  key={s.label}
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    borderRadius: 14,
                    padding: "16px 12px",
                    textAlign: "center",
                  }}
                >
                  <div style={{ fontSize: 24, fontWeight: 700, color: "#e2e8f0" }}>{s.value}</div>
                  <div style={{ fontSize: 11, color: "#64748b", marginTop: 2 }}>{s.sub}</div>
                  <div style={{ fontSize: 12, color: "#94a3b8", marginTop: 4 }}>{s.label}</div>
                </div>
              ))}
            </div>

            {/* Knowledge map */}
            <div
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: 16,
                padding: "20px",
                marginBottom: 28,
              }}
            >
              <h3
                style={{
                  fontSize: 15,
                  fontWeight: 700,
                  color: "#e2e8f0",
                  marginBottom: 16,
                  textAlign: "center",
                }}
              >
                🗺️ 知识地图：一次肺炎的跨学科串联
              </h3>
              {STAGES.map((s, i) => {
                const r = results[i];
                return (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      gap: 12,
                      marginBottom: i < STAGES.length - 1 ? 4 : 0,
                      alignItems: "stretch",
                    }}
                  >
                    {/* Timeline line */}
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        width: 28,
                        flexShrink: 0,
                      }}
                    >
                      <div
                        style={{
                          width: 22,
                          height: 22,
                          borderRadius: 11,
                          background: r?.correct ? "rgba(110,231,183,0.25)" : "rgba(252,165,165,0.25)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 11,
                          flexShrink: 0,
                        }}
                      >
                        {s.lensIcon}
                      </div>
                      {i < STAGES.length - 1 && (
                        <div
                          style={{
                            width: 1.5,
                            flex: 1,
                            background: "rgba(255,255,255,0.08)",
                            minHeight: 20,
                          }}
                        />
                      )}
                    </div>
                    <div style={{ paddingBottom: 16, flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: s.lensColor, marginBottom: 2 }}>
                        {s.lens}
                      </div>
                      <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.6 }}>
                        {s.aha.replace("🎯 啊哈时刻：", "")}
                      </div>
                    </div>
                    <div
                      style={{
                        fontSize: 14,
                        alignSelf: "flex-start",
                        marginTop: 2,
                      }}
                    >
                      {r?.correct ? "✅" : "❌"}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Wrong answers review */}
            {results.some((r) => !r.correct) && (
              <div
                style={{
                  background: "rgba(252,165,165,0.05)",
                  border: "1px solid rgba(252,165,165,0.15)",
                  borderRadius: 14,
                  padding: "18px 20px",
                  marginBottom: 24,
                }}
              >
                <h4 style={{ fontSize: 14, fontWeight: 600, color: "#fca5a5", marginBottom: 12 }}>
                  📝 错题回顾
                </h4>
                {results.map((r, i) => {
                  if (r.correct) return null;
                  const s = STAGES[i];
                  return (
                    <div
                      key={i}
                      style={{
                        marginBottom: 14,
                        paddingBottom: 14,
                        borderBottom:
                          i < results.length - 1 ? "1px solid rgba(255,255,255,0.06)" : "none",
                      }}
                    >
                      <div style={{ fontSize: 12, color: s.lensColor, marginBottom: 4 }}>
                        {s.lensIcon} {s.lens} · {s.title}
                      </div>
                      <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.7, marginBottom: 6 }}>
                        {s.question}
                      </div>
                      <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.7 }}>
                        → {s.explanation}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <button
              onClick={restart}
              style={{
                width: "100%",
                background: "linear-gradient(135deg, #6ee7b7, #34d399)",
                color: "#0a0e1a",
                border: "none",
                borderRadius: 12,
                padding: "14px",
                fontSize: 15,
                fontWeight: 700,
                cursor: "pointer",
                fontFamily: "inherit",
              }}
            >
              🔄 再来一次
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
