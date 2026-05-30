import { createBrowserRouter } from "react-router";
import { ProductScanner } from "./components/ProductScanner";
import { ProductComparison } from "./components/ProductComparison";
import { ProductDetail } from "./components/ProductDetail";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: ProductScanner,
  },
  {
    path: "/compare/:productId",
    Component: ProductComparison,
  },
  {
    path: "/product/:productId",
    Component: ProductDetail,
  },
]);
