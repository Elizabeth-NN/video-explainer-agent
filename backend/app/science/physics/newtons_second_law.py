from manim import *


class NewtonsSecondLaw(Scene):
    """Show how net force and mass determine acceleration."""

    def construct(self):
        title = Text("Newton's Second Law", font_size=34, color=TEAL)
        title.to_edge(UP)

        equation = MathTex(r"F_{\mathrm{net}} = ma", font_size=48)
        equation.next_to(title, DOWN, buff=0.35)

        block = Square(side_length=1.15, color=BLUE, fill_opacity=0.85)
        block.move_to(LEFT * 2 + DOWN * 0.9)

        mass_label = MathTex("m", font_size=32)
        mass_label.move_to(block.get_center())

        force_arrow = Arrow(
            block.get_right(),
            block.get_right() + RIGHT * 2,
            buff=0.05,
            color=YELLOW,
            stroke_width=6,
        )
        force_label = Text("Net force", font_size=20, color=YELLOW)
        force_label.next_to(force_arrow, UP, buff=0.12)

        acceleration_arrow = Arrow(
            block.get_bottom() + DOWN * 0.35,
            block.get_bottom() + DOWN * 0.35 + RIGHT * 1.4,
            buff=0,
            color=GREEN,
            stroke_width=5,
        )
        acceleration_label = Text("Acceleration", font_size=18, color=GREEN)
        acceleration_label.next_to(acceleration_arrow, DOWN, buff=0.1)

        self.play(Write(title), Write(equation))
        self.play(FadeIn(block), Write(mass_label))
        self.play(GrowArrow(force_arrow), FadeIn(force_label))
        self.play(GrowArrow(acceleration_arrow), FadeIn(acceleration_label))
        self.play(block.animate.shift(RIGHT * 1.5),
                  mass_label.animate.shift(RIGHT * 1.5))
        self.wait(1)
