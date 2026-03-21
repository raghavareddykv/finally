import { render, screen } from "@testing-library/react";
import { ConnectionStatus } from "@/components/ConnectionStatus";

describe("ConnectionStatus", () => {
  it("renders connected state with green dot", () => {
    render(<ConnectionStatus status="connected" />);
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("renders reconnecting state", () => {
    render(<ConnectionStatus status="reconnecting" />);
    expect(screen.getByText("Reconnecting")).toBeInTheDocument();
  });

  it("renders disconnected state", () => {
    render(<ConnectionStatus status="disconnected" />);
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
  });
});
