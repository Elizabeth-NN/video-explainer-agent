from manim import *


class Kinematics(Scene):
    """Illustrate changing position and velocity over time."""

    def construct(self):
        title = Text("Kinematics: Motion Over Time", font_size=32, color=TEAL)
        title.to_edge(UP)

        axes = Axes(
            x_range=[0, 5, 1],
            y_range=[0, 5, 1],
            x_length=8,
            y_length=4,
            tips=False,
            axis_config={"include_numbers": True, "font_size": 18},
        ).shift(DOWN * 0.65)

        x_label = Text("Time", font_size=20)
        x_label.next_to(axes.x_axis, DOWN, buff=0.25)

        y_label = Text("Position", font_size=20)
        y_label.rotate(PI / 2)
        y_label.next_to(axes.y_axis, LEFT, buff=0.3)

        curve = axes.plot(
            lambda t: 0.15 * t**2 + 0.4 * t,
            x_range=[0, 4],
            color=YELLOW,
            stroke_width=4,
        )

        moving_dot = Dot(axes.c2p(0, 0), color=TEAL, radius=0.09)
        self.play(Write(title), Create(axes))
        self.play(FadeIn(x_label), FadeIn(y_label), Create(curve))
        self.play(MoveAlongPath(moving_dot, curve), run_time=4, rate_func=linear)
        self.wait(1)
