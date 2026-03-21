import { render, screen, act } from "@testing-library/react";
import { MarketProvider, useMarket } from "@/lib/market-context";
import type { PriceUpdate } from "@/lib/types";

function TestConsumer() {
  const { state, handlePriceUpdate, setConnectionStatus, selectTicker } =
    useMarket();

  return (
    <div>
      <div data-testid="connection">{state.connectionStatus}</div>
      <div data-testid="selected">{state.selectedTicker ?? "none"}</div>
      <div data-testid="tickers">{Object.keys(state.tickers).join(",")}</div>
      {Object.entries(state.tickers).map(([ticker, data]) => (
        <div key={ticker} data-testid={`price-${ticker}`}>
          {data.price}
        </div>
      ))}
      <button
        data-testid="add-price"
        onClick={() =>
          handlePriceUpdate({
            ticker: "AAPL",
            price: 190.5,
            previous_price: 190.0,
            timestamp: "2024-01-01T00:00:00Z",
            change_direction: "up",
          })
        }
      />
      <button
        data-testid="set-connected"
        onClick={() => setConnectionStatus("connected")}
      />
      <button
        data-testid="select-aapl"
        onClick={() => selectTicker("AAPL")}
      />
      <button
        data-testid="deselect"
        onClick={() => selectTicker(null)}
      />
    </div>
  );
}

describe("MarketContext", () => {
  it("starts with default state", () => {
    render(
      <MarketProvider>
        <TestConsumer />
      </MarketProvider>
    );

    expect(screen.getByTestId("connection")).toHaveTextContent("disconnected");
    expect(screen.getByTestId("selected")).toHaveTextContent("none");
    expect(screen.getByTestId("tickers")).toHaveTextContent("");
  });

  it("handles price updates", () => {
    render(
      <MarketProvider>
        <TestConsumer />
      </MarketProvider>
    );

    act(() => {
      screen.getByTestId("add-price").click();
    });

    expect(screen.getByTestId("tickers")).toHaveTextContent("AAPL");
    expect(screen.getByTestId("price-AAPL")).toHaveTextContent("190.5");
  });

  it("updates connection status", () => {
    render(
      <MarketProvider>
        <TestConsumer />
      </MarketProvider>
    );

    act(() => {
      screen.getByTestId("set-connected").click();
    });

    expect(screen.getByTestId("connection")).toHaveTextContent("connected");
  });

  it("selects and deselects ticker", () => {
    render(
      <MarketProvider>
        <TestConsumer />
      </MarketProvider>
    );

    act(() => {
      screen.getByTestId("select-aapl").click();
    });
    expect(screen.getByTestId("selected")).toHaveTextContent("AAPL");

    act(() => {
      screen.getByTestId("deselect").click();
    });
    expect(screen.getByTestId("selected")).toHaveTextContent("none");
  });

  it("accumulates price history up to max points", () => {
    const TestHistory = () => {
      const { state, handlePriceUpdate } = useMarket();
      const history = state.tickers["TEST"]?.priceHistory ?? [];
      return (
        <div>
          <div data-testid="history-len">{history.length}</div>
          <button
            data-testid="push"
            onClick={() =>
              handlePriceUpdate({
                ticker: "TEST",
                price: Math.random() * 100,
                previous_price: 50,
                timestamp: new Date().toISOString(),
                change_direction: "up",
              })
            }
          />
        </div>
      );
    };

    render(
      <MarketProvider>
        <TestHistory />
      </MarketProvider>
    );

    // Push 65 price points (max is 60)
    for (let i = 0; i < 65; i++) {
      act(() => {
        screen.getByTestId("push").click();
      });
    }

    expect(screen.getByTestId("history-len")).toHaveTextContent("60");
  });
});
