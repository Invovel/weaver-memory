"""Generate the README architecture diagram as a PNG asset."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1800
HEIGHT = 1160
BACKGROUND = "#F6F8FC"
INK = "#172033"
MUTED = "#5C6880"
ARROW = "#52627A"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


TITLE = font(54, bold=True)
SUBTITLE = font(25)
BOX_TITLE = font(30, bold=True)
BOX_TEXT = font(21)
SMALL = font(18)


def center_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str,
                text_font: ImageFont.FreeTypeFont, fill: str = INK) -> None:
    left, top, right, bottom = box
    bounds = draw.textbbox((0, 0), text, font=text_font)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    draw.text(((left + right - width) / 2, (top + bottom - height) / 2 - 2),
              text, font=text_font, fill=fill)


def box(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], title: str,
        lines: list[str], fill: str, border: str) -> None:
    draw.rounded_rectangle(rect, radius=28, fill=fill, outline=border, width=4)
    left, top, right, _ = rect
    draw.text((left + 26, top + 20), title, font=BOX_TITLE, fill=INK)
    y = top + 72
    for line in lines:
        draw.text((left + 28, y), line, font=BOX_TEXT, fill=MUTED)
        y += 31


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int],
          label: str = "", color: str = ARROW) -> None:
    draw.line([start, end], fill=color, width=5)
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    length = max((dx * dx + dy * dy) ** 0.5, 1)
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    size = 16
    wing = 8
    tip = (x2, y2)
    base = (x2 - ux * size, y2 - uy * size)
    draw.polygon(
        [
            tip,
            (base[0] + px * wing, base[1] + py * wing),
            (base[0] - px * wing, base[1] - py * wing),
        ],
        fill=color,
    )
    if label:
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        bounds = draw.textbbox((0, 0), label, font=SMALL)
        text_width = bounds[2] - bounds[0]
        draw.rounded_rectangle(
            (mid_x - text_width / 2 - 8, mid_y - 17, mid_x + text_width / 2 + 8, mid_y + 13),
            radius=8,
            fill=BACKGROUND,
        )
        draw.text((mid_x - text_width / 2, mid_y - 14), label, font=SMALL, fill=MUTED)


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.text((85, 55), "MemoryWeaver Runtime Architecture", font=TITLE, fill=INK)
    draw.text(
        (88, 125),
        "LLM proposes. Harness judges. Deterministic lifecycle gates surround model actions.",
        font=SUBTITLE,
        fill=MUTED,
    )

    lifecycle = [
        ((105, 170, 470, 218), "1  Environment Contract", "#E9F2FF", "#4D8FD8"),
        ((500, 170, 865, 218), "2  Procedural Skills", "#F0EBFF", "#8067C8"),
        ((895, 170, 1260, 218), "3  Action Realization", "#FDEDDD", "#C87837"),
        ((1290, 170, 1685, 218), "4  Trajectory Regulation", "#E7F7F1", "#3C9B79"),
    ]
    for rect, label, fill, border in lifecycle:
        draw.rounded_rectangle(rect, radius=18, fill=fill, outline=border, width=3)
        center_text(draw, rect, label, SMALL, fill=INK)

    user = (90, 230, 390, 405)
    harness = (585, 205, 1215, 420)
    rag = (95, 500, 475, 695)
    graph = (545, 500, 925, 695)
    pattern = (995, 500, 1375, 695)
    llm = (1445, 500, 1710, 695)
    cli = (1445, 795, 1710, 980)
    feedback = (995, 795, 1375, 980)
    badcase = (545, 795, 925, 980)
    checkpoint = (95, 795, 475, 980)

    box(draw, user, "User / Agent Client", ["query", "confirmation", "correction"], "#E9F2FF", "#4D8FD8")
    box(draw, harness, "MemoryWeaver Harness", ["contract + policy gates", "context fusion + router", "promotion / demotion", "anti-pollution judge"], "#FFF0D8", "#D58A28")
    box(draw, rag, "RAG Evidence Layer", ["documents + chunks", "hybrid retrieval", "citations + versions"], "#E7F7F1", "#3C9B79")
    box(draw, graph, "GBrain Graph", ["entities + tags", "relationships", "temporal context"], "#F0EBFF", "#8067C8")
    box(draw, pattern, "Procedural Skills", ["Layer 3 patterns", "avoidance memory", "fast-path context"], "#FFEAF1", "#C65D83")
    box(draw, llm, "LLM", ["reason", "propose", "never self-verify"], "#EAF0FF", "#647FD0")
    box(draw, cli, "ActionGate / Tools", ["schema + permission", "sandboxed jobs", "idempotency"], "#FDEDDD", "#C87837")
    box(draw, feedback, "Trajectory Regulation", ["tool feedback", "loop + stagnation", "recovery signal"], "#E7F7F1", "#3C9B79")
    box(draw, badcase, "Bad-Case Loop", ["triage + cluster", "regression fixtures", "progressive tuning"], "#FFE9E9", "#C95D5D")
    box(draw, checkpoint, "Checkpoint Store", ["session continuity", "event journal", "crash recovery"], "#E9F2FF", "#4D8FD8")

    arrow(draw, (390, 295), (585, 295), "request")
    arrow(draw, (720, 420), (290, 500), "evidence plan")
    arrow(draw, (835, 420), (735, 500), "graph plan")
    arrow(draw, (970, 420), (1185, 500), "pattern plan")
    arrow(draw, (1215, 295), (1575, 500), "bounded context")
    arrow(draw, (1575, 695), (1575, 795), "ActionProposal")
    arrow(draw, (1445, 885), (1375, 885), "result")
    arrow(draw, (1185, 795), (1185, 695), "skill feedback")
    arrow(draw, (995, 885), (925, 885), "failure signal")
    arrow(draw, (545, 885), (475, 885), "checkpoint")
    arrow(draw, (285, 795), (690, 420), "resume")

    center_text(
        draw,
        (90, 1040, 1710, 1110),
        "Online path: retrieve -> judge -> reason -> act -> observe -> checkpoint -> improve",
        SUBTITLE,
        fill=INK,
    )

    output = Path(__file__).resolve().parents[1] / "docs" / "assets" / "memoryweaver-architecture.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)
    print(output)


if __name__ == "__main__":
    main()
