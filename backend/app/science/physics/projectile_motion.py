from manim import *


class ProjectileMotion(Scene):
    """Illustrate ideal projectile motion with a parabolic trajectory."""

    def construct(self):
        title = Text("Projectile Motion", font_size=36, color=TEAL)
        title.to_edge(UP)

        axes = Axes(
            x_range=[0, 10, 2],
            y_range=[0, 5, 1],
            x_length=9,
            y_length=4,
            tips=False,
            axis_config={"include_numbers": False},
        )
        axes.to_edge(DOWN, buff=0.7)

        x_label = Text("Horizontal distance", font_size=18)
        x_label.next_to(axes, DOWN, buff=0.25)

        y_label = Text("Height", font_size=18)
        y_label.rotate(PI / 2)
        y_label.next_to(axes, LEFT, buff=0.25)

        def trajectory(x):
            return 0.8 * x - 0.08 * x**2

        path = axes.plot(
            trajectory,
            x_range=[0, 10],
            color=YELLOW,
            stroke_width=4,
        )

        ball = Dot(axes.c2p(0, trajectory(0)), color=TEAL, radius=0.09)
        ball_label = Text("Projectile", font_size=18, color=TEAL)
        ball_label.next_to(ball, UP, buff=0.15)

        self.play(Write(title), Create(axes))
        self.play(FadeIn(x_label), FadeIn(y_label))
        self.play(Create(path), FadeIn(ball), FadeIn(ball_label))

        self.play(
            MoveAlongPath(ball, path),
            ball_label.animate.shift(RIGHT * 5),
            run_time=4,
            rate_func=linear,
        )

        self.wait(1)
