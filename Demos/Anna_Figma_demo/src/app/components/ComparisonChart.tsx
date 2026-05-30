import { 
  RadarChart, 
  PolarGrid, 
  PolarAngleAxis, 
  PolarRadiusAxis, 
  Radar, 
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell
} from "recharts";
import { Product } from "../data/products";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";

interface ComparisonChartProps {
  currentProduct: Product;
  recommendedProduct: Product;
}

export function ComparisonChart({ currentProduct, recommendedProduct }: ComparisonChartProps) {
  // Prepare data for radar chart (normalized to 0-100 scale)
  const radarData = [
    {
      dimension: "Nutri-Score",
      current: currentProduct.nutriScore,
      recommended: recommendedProduct.nutriScore,
    },
    {
      dimension: "Eco-Score",
      current: currentProduct.ecoScore,
      recommended: recommendedProduct.ecoScore,
    },
    {
      dimension: "Protein",
      current: Math.min((currentProduct.protein / 30) * 100, 100),
      recommended: Math.min((recommendedProduct.protein / 30) * 100, 100),
    },
    {
      dimension: "Low Sugar",
      current: Math.max(100 - (currentProduct.sugar / 50) * 100, 0),
      recommended: Math.max(100 - (recommendedProduct.sugar / 50) * 100, 0),
    },
    {
      dimension: "Fiber",
      current: Math.min((currentProduct.fiber / 10) * 100, 100),
      recommended: Math.min((recommendedProduct.fiber / 10) * 100, 100),
    },
    {
      dimension: "Low CO₂",
      current: Math.max(100 - (currentProduct.co2 / 20) * 100, 0),
      recommended: Math.max(100 - (recommendedProduct.co2 / 20) * 100, 0),
    },
  ];

  // Prepare data for bar chart (actual values)
  const barData = [
    {
      name: "Nutri-Score",
      current: currentProduct.nutriScore,
      recommended: recommendedProduct.nutriScore,
      unit: "/100",
    },
    {
      name: "Eco-Score",
      current: currentProduct.ecoScore,
      recommended: recommendedProduct.ecoScore,
      unit: "/100",
    },
    {
      name: "Price",
      current: currentProduct.price,
      recommended: recommendedProduct.price,
      unit: "$",
    },
    {
      name: "CO₂",
      current: currentProduct.co2,
      recommended: recommendedProduct.co2,
      unit: "kg",
      invert: true, // Lower is better
    },
    {
      name: "Protein",
      current: currentProduct.protein,
      recommended: recommendedProduct.protein,
      unit: "g",
    },
    {
      name: "Sugar",
      current: currentProduct.sugar,
      recommended: recommendedProduct.sugar,
      unit: "g",
      invert: true,
    },
    {
      name: "Fiber",
      current: currentProduct.fiber,
      recommended: recommendedProduct.fiber,
      unit: "g",
    },
    {
      name: "Calories",
      current: currentProduct.calories,
      recommended: recommendedProduct.calories,
      unit: "kcal",
    },
  ];

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-white p-3 border rounded-lg shadow-lg">
          <p className="font-medium mb-2">{data.name}</p>
          <div className="space-y-1 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-gray-500 rounded"></div>
              <span>Your Product: {data.current}{data.unit}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-green-500 rounded"></div>
              <span>Alternative: {data.recommended}{data.unit}</span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <Tabs defaultValue="radar" className="w-full">
      <TabsList className="grid w-full grid-cols-2 mb-6">
        <TabsTrigger value="radar">Multi-Dimensional View</TabsTrigger>
        <TabsTrigger value="bars">Detailed Metrics</TabsTrigger>
      </TabsList>

      <TabsContent value="radar">
        <div className="h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="dimension" />
              <PolarRadiusAxis angle={90} domain={[0, 100]} />
              <Radar
                name="Your Product"
                dataKey="current"
                stroke="#6b7280"
                fill="#6b7280"
                fillOpacity={0.3}
              />
              <Radar
                name="Recommended"
                dataKey="recommended"
                stroke="#16a34a"
                fill="#16a34a"
                fillOpacity={0.5}
              />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 p-4 bg-blue-50 rounded-lg">
          <p className="text-sm text-gray-700">
            <strong>How to read:</strong> Each axis represents a different quality metric normalized to a 0-100 scale. 
            Larger areas indicate better overall performance across multiple dimensions.
          </p>
        </div>
      </TabsContent>

      <TabsContent value="bars">
        <div className="h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={barData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
              <YAxis />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar dataKey="current" name="Your Product" fill="#6b7280" />
              <Bar dataKey="recommended" name="Recommended" fill="#16a34a" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        
        <div className="mt-6 grid grid-cols-2 gap-4">
          {barData.map((item) => {
            const isBetter = item.invert 
              ? item.recommended < item.current 
              : item.recommended > item.current;
            const difference = item.invert
              ? ((item.current - item.recommended) / item.current * 100).toFixed(1)
              : ((item.recommended - item.current) / item.current * 100).toFixed(1);
            
            return (
              <div key={item.name} className="p-3 bg-gray-50 rounded-lg">
                <div className="text-sm text-gray-600 mb-1">{item.name}</div>
                <div className="flex items-baseline justify-between">
                  <div>
                    <span className="text-gray-700 line-through mr-2">
                      {item.current}{item.unit}
                    </span>
                    <span className={isBetter ? "text-green-700 font-medium" : "text-gray-700 font-medium"}>
                      {item.recommended}{item.unit}
                    </span>
                  </div>
                  {isBetter && (
                    <span className="text-xs text-green-600 font-medium">
                      {item.invert ? '↓' : '↑'} {Math.abs(parseFloat(difference))}%
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </TabsContent>
    </Tabs>
  );
}
