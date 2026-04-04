export type StockBar = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type PriceResponse = {
  stock_id: string;
  prices: StockBar[];
};

export type StockState = {
  stockId: string;
  stockName: string;
  startDate: string;
  endDate: string;
};
