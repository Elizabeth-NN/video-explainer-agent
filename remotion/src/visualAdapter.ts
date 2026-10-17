import { z } from "zod";

const zNode = z.object({
  label: z.string().min(1),
  icon: z.string().default("dot"),
  color: z.string().optional(),
});
const base = { title: z.string().optional(), footnote: z.string().optional() };

export const VisualSpecSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("flow"), ...base, nodes: z.array(zNode).min(2).max(4) }),
  z.object({
    type: z.literal("hub"), ...base, center: zNode,
    satellites: z.array(zNode).min(2).max(6), direction: z.enum(["in", "out"]).optional(),
  }),
  z.object({
    type: z.literal("bars"), ...base, suffix: z.string().optional(),
    bars: z.array(z.object({ label: z.string(), value: z.number().nonnegative(), color: z.string().optional() })).min(2).max(6),
  }),
  z.object({
    type: z.literal("sequence"), ...base,
    steps: z.array(z.object({ label: z.string(), detail: z.string().optional(), icon: z.string().optional() })).min(2).max(5),
  }),
  z.object({
    type: z.literal("cycle"), ...base, centerLabel: z.string().optional(),
    stages: z.array(z.object({ label: z.string(), color: z.string().optional() })).min(3).max(6),
  }),
  z.object({
    type: z.literal("layers"), ...base,
    layers: z.array(z.object({ label: z.string(), note: z.string().optional(), color: z.string().optional() })).min(2).max(6),
    carriers: z.array(z.object({
      label: z.string(), fromLayer: z.number().int(), toLayer: z.number().int(), color: z.string().optional(),
    })).optional(),
  }),
  z.object({
    type: z.literal("anatomy"), ...base,
    subject: z.enum(["circle", "capsule", "block", "blob"]).catch("blob"),
    parts: z.array(z.object({ label: z.string(), note: z.string().optional() })).min(2).max(6),
  }),
  z.object({
    type: z.literal("comparison"), ...base,
    left: z.object({ heading: z.string(), points: z.array(z.string()).min(1).max(4), color: z.string().optional() }),
    right: z.object({ heading: z.string(), points: z.array(z.string()).min(1).max(4), color: z.string().optional() }),
  }),
  z.object({
    type: z.literal("scene-graph"), ...base,
    nodes: z.array(z.object({
      id: z.string(), label: z.string(), x: z.number().min(0).max(1000), y: z.number().min(0).max(430),
      size: z.number().optional(), color: z.string().optional(), appearAt: z.number().optional(),
    })).min(2).max(10),
    links: z.array(z.object({
      from: z.string(), to: z.string(), label: z.string().optional(), color: z.string().optional(),
      style: z.enum(["solid", "dashed"]).optional(), appearAt: z.number().optional(),
    })),
    groups: z.array(z.any()).optional(),
  }),
  z.object({ type: z.literal("illustration"), ...base, id: z.string(), focus: z.any().optional() }),
]);
