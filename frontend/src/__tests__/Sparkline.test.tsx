import { render } from "@testing-library/react";
import { Sparkline } from "@/components/Sparkline";

describe("Sparkline", () => {
  it("renders nothing with fewer than 2 data points", () => {
    const { container } = render(<Sparkline data={[100]} />);
    expect(container.querySelector("svg")).toBeNull();
  });

  it("renders SVG with valid data", () => {
    const { container } = render(
      <Sparkline data={[100, 102, 101, 103, 105]} />
    );
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("width")).toBe("80");
    expect(svg?.getAttribute("height")).toBe("24");
  });

  it("uses green stroke when price is up", () => {
    const { container } = render(<Sparkline data={[100, 105]} />);
    const polyline = container.querySelector("polyline");
    expect(polyline?.getAttribute("stroke")).toBe("var(--color-trade-green)");
  });

  it("uses red stroke when price is down", () => {
    const { container } = render(<Sparkline data={[105, 100]} />);
    const polyline = container.querySelector("polyline");
    expect(polyline?.getAttribute("stroke")).toBe("var(--color-trade-red)");
  });

  it("renders with custom dimensions", () => {
    const { container } = render(
      <Sparkline data={[100, 105]} width={120} height={40} />
    );
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("width")).toBe("120");
    expect(svg?.getAttribute("height")).toBe("40");
  });
});
