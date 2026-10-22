from manim import *


class PotentialEnergy(Scene):
    """Compare gravitational potential energy at two heights."""

    def construct(self):
        title = Text("Gravitational Potential Energy", font_size=30, color=TEAL)
        title.to_edge(UP)

        equation = MathTex(r"PE = mgh", font_size=44)
        equation.next_to(title, DOWN, buff=0.25)

        ground = Line(LEFT * 5 + DOWN * 2.5, RIGHT * 5 + DOWN * 2.5)

        low_platform = Line(LEFT * 2.8 + DOWN * 1.7, LEFT * 0.7 + DOWN * 1.7)
        high_platform = Line(RIGHT * 0.7 + UP * 0.8, RIGHT * 2.8 + UP * 0.8)

        low_block = Square(side_length=0.65, color=BLUE, fill_opacity=0.85)
        low_block.move_to(LEFT * 1.75 + DOWN * 1.35)

        high_block = Square(side_length=0.65, color=GREEN, fill_opacity=0.85)
        high_block.move_to(RIGHT * 1.75 + UP * 1.15)

        low_label = Text("Lower height", font_size=18)
        low_label.next_to(low_platform, DOWN, buff=0.2)

        high_label = Text("Greater height", font_size=18)
        high_label.next_to(high_platform, UP, buff=0.2)

        comparison = Text(
            "Greater height means greater PE for the same mass",
            font_size=19,
            color=YELLOW,
        )
        comparison.to_edge(DOWN, buff=0.25)

        self.play(Write(title), Write(equation))
        self.play(Create(ground), Create(low_platform), Create(high_platform))
        self.play(FadeIn(low_block), FadeIn(high_block))
        self.play(Write(low_label), Write(high_label))
        self.play(Write(comparison))
        self.wait(1)
