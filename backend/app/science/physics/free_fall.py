from manim import *


class FreeFall(Scene):
    """Show an object falling while its downward velocity increases."""

    def construct(self):
        title = Text("Free Fall", font_size=36, color=TEAL)
        title.to_edge(UP)

        note = Text(
            "Ignoring air resistance",
            font_size=22,
            color=GRAY_B,
        )
        note.next_to(title, DOWN, buff=0.2)

        ground = Line(LEFT * 4.5 + DOWN * 2.7, RIGHT * 4.5 + DOWN * 2.7)
        ball = Dot(UP * 2.1, radius=0.16, color=YELLOW)

        gravity_arrow = Arrow(
            ball.get_bottom(),
            ball.get_bottom() + DOWN * 0.9,
            buff=0.05,
            color=RED,
            stroke_width=5,
        )
        gravity_label = MathTex("g", color=RED, font_size=32)
        gravity_label.next_to(gravity_arrow, RIGHT, buff=0.15)

        self.play(Write(title), FadeIn(note), Create(ground))
        self.play(FadeIn(ball))
        self.play(GrowArrow(gravity_arrow), FadeIn(gravity_label))
        self.play(
            ball.animate.move_to(DOWN * 2.35),
            gravity_arrow.animate.shift(DOWN * 2.0),
            gravity_label.animate.shift(DOWN * 2.0),
            run_time=2,
            rate_func=rate_functions.ease_in_quad,
        )
        self.wait(1)
