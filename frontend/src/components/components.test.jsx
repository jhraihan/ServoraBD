import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { matchServices } from "../hooks/useCatalogue";
import { useCompareStore } from "../store/compare";
import { BookingStateBadge, BookingTimeline, ProviderCard, StarInput, Stars } from "./domain";
import { TrustBadge, TrustBreakdown } from "./Trust";
import { ConfirmAction, ErrorMessage, PasswordInput } from "./ui";

const trust = {
  score: 53.48,
  tier: "rising",
  penalties: 0,
  verification: { phone: true, identity: false, skill: false, address: false },
  evidence: {
    jobsCompleted: 18, jobsAccepted: 30, jobsCancelled: 12,
    completionRate: 60, cancellationRate: 40, medianResponseSeconds: 6 * 3600,
  },
  factors: [
    { key: "f4_cancellation", label: "Cancellation discipline", score: 16.4, weight: 0.15, contribution: 2.46 },
    { key: "f6_reviews", label: "Review quality", score: 91.7, weight: 0.2, contribution: 18.35 },
  ],
};

describe("TrustBadge", () => {
  it("shows the tier with the rounded score", () => {
    render(<TrustBadge score="84.19" tier="rising" />);
    expect(screen.getByText("Rising")).toBeInTheDocument();
    expect(screen.getByText("84")).toBeInTheDocument();
  });
});

describe("TrustBreakdown", () => {
  it("shows the evidence, not just a number", () => {
    render(<TrustBreakdown trust={trust} />);
    expect(screen.getByText("18")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByText("6 hr")).toBeInTheDocument();
    expect(screen.getByText("Identity verified (NID)")).toBeInTheDocument();
  });

  it("flags a high cancellation rate", () => {
    render(<TrustBreakdown trust={trust} />);
    expect(screen.getByText("40%")).toHaveClass("text-rose-700");
  });

  it("reveals the weighted factors on request", async () => {
    render(<TrustBreakdown trust={trust} />);
    expect(screen.queryByText("Cancellation discipline")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "How trust is scored" }));

    expect(screen.getByText("Cancellation discipline")).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: "Review quality" })).toHaveAttribute("aria-valuenow", "92");
  });
});

describe("BookingTimeline", () => {
  it("lists each transition with who made it", () => {
    render(
      <BookingTimeline
        events={[
          { id: 1, fromState: null, toState: "scheduled", actor: "provider", reason: "", metadata: {}, createdAt: "2026-09-01T04:00:00Z" },
          { id: 2, fromState: "scheduled", toState: "cancelled_customer", actor: "customer", reason: "Plans changed", metadata: {}, createdAt: "2026-09-01T05:00:00Z" },
        ]}
      />,
    );
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Scheduled");
    expect(items[1]).toHaveTextContent("Cancelled by customer");
    expect(items[1]).toHaveTextContent("“Plans changed”");
  });
});

describe("BookingStateBadge", () => {
  it("uses a role-neutral label", () => {
    render(<BookingStateBadge state="awaiting_confirm" />);
    expect(screen.getByText("Awaiting confirmation")).toBeInTheDocument();
  });
});

describe("Stars", () => {
  it("announces the rating to screen readers", () => {
    render(<Stars value={4} />);
    expect(screen.getByRole("img", { name: "4 out of 5 stars" })).toBeInTheDocument();
  });
});

describe("ProviderCard", () => {
  const provider = {
    id: 7, displayName: "Kamal Hossain", experienceYears: 14,
    identityVerified: false, skillVerified: false, phoneVerified: true,
    trustScore: "71.43", trustTier: "new", jobsCompleted: 1, jobsCancelled: 0,
    medianResponseSeconds: null, fromPrice: "1800.00", serviceAreas: [],
  };

  beforeEach(() => {
    useCompareStore.setState({ ids: [] });
  });

  function renderCard(p = provider) {
    return render(
      <MemoryRouter>
        <ProviderCard provider={p} serviceId={13} />
      </MemoryRouter>,
    );
  }

  it("marks unverified providers visibly", () => {
    renderCard();
    expect(screen.getByText("Unverified")).toBeInTheDocument();
  });

  it("carries the chosen service through to the profile link", () => {
    renderCard();
    expect(screen.getByRole("link", { name: "View" })).toHaveAttribute("href", "/providers/7?service=13");
  });

  it("stops adding to comparison at three providers", async () => {
    useCompareStore.setState({ ids: [1, 2, 3] });
    renderCard();
    expect(screen.getByRole("button", { name: "Compare" })).toBeDisabled();
  });

  it("toggles comparison", async () => {
    renderCard();
    await userEvent.click(screen.getByRole("button", { name: "Compare" }));
    expect(useCompareStore.getState().ids).toEqual([7]);
    expect(screen.getByRole("button", { name: "Comparing" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("ConfirmAction", () => {
  it("asks before running a destructive action", async () => {
    const onConfirm = vi.fn();
    render(<ConfirmAction label="Withdraw" prompt="Withdraw this request?" confirmLabel="Yes, withdraw" onConfirm={onConfirm} />);

    await userEvent.click(screen.getByRole("button", { name: "Withdraw" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Keep" })).toHaveFocus();

    await userEvent.click(screen.getByRole("button", { name: "Yes, withdraw" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("backs out without acting", async () => {
    const onConfirm = vi.fn();
    render(<ConfirmAction label="Remove" prompt="Remove this service?" confirmLabel="Yes, remove" onConfirm={onConfirm} />);

    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    await userEvent.click(screen.getByRole("button", { name: "Keep" }));

    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
  });
});

describe("PasswordInput", () => {
  it("reveals and hides what was typed", async () => {
    render(
      <>
        <label htmlFor="pw">Password</label>
        <PasswordInput id="pw" value="secret123" onChange={() => {}} />
      </>,
    );
    const input = screen.getByLabelText("Password");
    expect(input).toHaveAttribute("type", "password");

    await userEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(input).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute("aria-pressed", "true");
  });
});

describe("StarInput", () => {
  it("names the rating as it is chosen", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<StarInput name="overall" label="Overall" value={0} onChange={onChange} />);

    await userEvent.click(screen.getByTestId("overall-4"));
    expect(onChange).toHaveBeenCalledWith(4);

    rerender(<StarInput name="overall" label="Overall" value={4} onChange={onChange} />);
    await userEvent.unhover(screen.getByTestId("overall-4"));
    expect(screen.getByText("Very good")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "4 stars" })).toHaveAttribute("aria-checked", "true");
  });
});

describe("ErrorMessage", () => {
  it("offers a retry when one is possible", async () => {
    const onRetry = vi.fn();
    render(<ErrorMessage error="Could not reach the server." onRetry={onRetry} />);

    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe("matchServices", () => {
  const services = [
    { id: 1, name: "Pipe leak repair", categoryName: "Plumbing", searchTerms: "leak water" },
    { id: 2, name: "AC servicing", categoryName: "AC & Refrigeration", searchTerms: "not cooling" },
    { id: 3, name: "Leak detection", categoryName: "Plumbing", searchTerms: "" },
  ];

  it("returns everything for an empty term", () => {
    expect(matchServices(services, "  ")).toHaveLength(3);
  });

  it("matches problems as well as names, best match first", () => {
    expect(matchServices(services, "leak").map((s) => s.id)).toEqual([3, 1]);
    expect(matchServices(services, "not cooling").map((s) => s.id)).toEqual([2]);
  });
});
