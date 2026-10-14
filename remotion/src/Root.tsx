import React from "react";
import { Composition } from "remotion";
import inputProps from "../input-props.json";
import { Explainer, type ExplainerProps } from "./Explainer";

const props = inputProps as ExplainerProps;
const durationInFrames = props.scenes.reduce(
  (total, scene) => total + scene.durationInFrames,
  0,
);

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Explainer"
      component={Explainer}
      durationInFrames={durationInFrames}
      fps={props.fps}
      width={props.width}
      height={props.height}
      defaultProps={props}
    />
  );
};
