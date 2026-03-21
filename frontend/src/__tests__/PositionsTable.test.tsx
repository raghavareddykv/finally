import { render, screen } from "@testing-library/react";
import { PositionsTable } from "@/components/PositionsTable";
import * as portfolioContext from "@/lib/portfolio-context";

jest.mock("@/lib/portfolio-context");

const mockUsePortfolioContext =
  portfolioContext.usePortfolioContext as jest.MockedFunction<
    typeof portfolioContext.usePortfolioContext
  >;

describe("PositionsTable", () => {
  it("shows loading state", () => {
    mockUsePortfolioContext.mockReturnValue({
      portfolio: null,
      history: [],
      loading: true,
      refresh: jest.fn(),
    });

    render(<PositionsTable />);
    expect(screen.getByText("Loading positions...")).toBeInTheDocument();
  });

  it("shows empty state when no positions", () => {
    mockUsePortfolioContext.mockReturnValue({
      portfolio: { cash: 10000, total_value: 10000, positions: [] },
      history: [],
      loading: false,
      refresh: jest.fn(),
    });

    render(<PositionsTable />);
    expect(screen.getByText("No open positions")).toBeInTheDocument();
  });

  it("renders position data correctly", () => {
    mockUsePortfolioContext.mockReturnValue({
      portfolio: {
        cash: 8000,
        total_value: 10500,
        positions: [
          {
            ticker: "AAPL",
            quantity: 10,
            avg_cost: 190.0,
            current_price: 200.0,
            unrealized_pnl: 100.0,
            pnl_pct: 5.26,
          },
          {
            ticker: "TSLA",
            quantity: 5,
            avg_cost: 250.0,
            current_price: 240.0,
            unrealized_pnl: -50.0,
            pnl_pct: -4.0,
          },
        ],
      },
      history: [],
      loading: false,
      refresh: jest.fn(),
    });

    render(<PositionsTable />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("TSLA")).toBeInTheDocument();
    expect(screen.getByText("+5.26%")).toBeInTheDocument();
    expect(screen.getByText("-4.00%")).toBeInTheDocument();
  });
});
