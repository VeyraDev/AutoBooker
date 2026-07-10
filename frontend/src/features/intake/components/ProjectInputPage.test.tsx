// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import ProjectInputPage from "@/features/intake/components/ProjectInputPage";

const flow = vi.hoisted(() => ({
  current: {
    step: "input" as const,
    intake: null as any,
    origin: null as any,
    originLabels: {
      idea_only: "我只有想法，想先确定方向",
      material_first: "我有资料，想整理成书",
      outline_first: "我有明确大纲，想扩写成书",
      manuscript_continue: "我有半成稿，想继续写或优化",
    },
    initializeOrigin: vi.fn(),
    start: vi.fn(),
    runUnderstanding: vi.fn(),
    confirmU: vi.fn(),
    confirmP: vi.fn(),
    applyCorrection: vi.fn(),
    uploadFile: vi.fn(),
    canUpload: false,
    loading: false,
  },
}));

vi.mock("@/features/intake/hooks/useIntakeFlow", () => ({
  ORIGIN_LABELS: flow.current.originLabels,
  useIntakeFlow: () => flow.current,
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  flow.current = {
    ...flow.current,
    step: "input",
    intake: null,
    origin: null,
    canUpload: false,
    loading: false,
  };
});

describe("ProjectInputPage", () => {
  it("uses existing intake origin instead of asking again", () => {
    flow.current = {
      ...flow.current,
      intake: {
        id: "intake-1",
        creation_origin: "material_first",
        raw_goal_text: "Use internal onboarding notes.",
        negative_constraints_text: "Avoid hype.",
        items: [],
      },
      origin: "material_first",
      canUpload: true,
    };

    render(<ProjectInputPage bookId="book-1" />);

    expect(screen.queryByText("选择创作起点")).toBeNull();
    expect(screen.getByText("项目输入")).toBeTruthy();
    expect(screen.getByText("我有资料，想整理成书")).toBeTruthy();
    expect(screen.getByDisplayValue("Use internal onboarding notes.")).toBeTruthy();
    expect((screen.getByRole("button", { name: "上传资料文件" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("initializes origin before upload is enabled", async () => {
    render(<ProjectInputPage bookId="book-1" />);

    await userEvent.click(screen.getByRole("button", { name: "我有资料，想整理成书" }));

    expect(flow.current.initializeOrigin).toHaveBeenCalledWith("material_first");
    expect(screen.getByText("项目输入")).toBeTruthy();
    expect((screen.getByRole("button", { name: "上传资料文件" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
