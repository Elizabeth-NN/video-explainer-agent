import React from "react";
import { z } from "zod";
import { arraySchema, arrayVisual } from "./array";
import { treeSchema, treeVisual } from "./tree";
import { chainSchema, chainVisual } from "./chain";
import { graphSchema, graphVisual } from "./graph";
import { exchangeSchema, exchangeVisual } from "./exchange";
import { codeSchema, codeVisual } from "./code";

export { PLANNER_CATALOG } from "./hints";

/**
 * To add a visual: write one file exporting { type, schema, Component, plannerHint },
 * add its hint to hints.ts, then add it to the two lists below. Nothing else changes.
 */
export const LIBRARY = [arrayVisual, treeVisual, chainVisual, graphVisual, exchangeVisual, codeVisual];

export const LibrarySchema = z.discriminatedUnion("type", [
  arraySchema,
  treeSchema,
  chainSchema,
  graphSchema,
  exchangeSchema,
  codeSchema,
]);
export type LibrarySpec = z.infer<typeof LibrarySchema>;

type AnyVisual = {
  type: string;
  Component: React.FC<{ spec: any; duration: number }>;
};

/** Returns the library module for a spec type, or undefined for the built-in visuals. */
export const findVisual = (type: string): AnyVisual | undefined =>
  (LIBRARY as AnyVisual[]).find((v) => v.type === type);
