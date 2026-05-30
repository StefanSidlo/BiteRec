export interface Product {
  id: string;
  name: string;
  brand: string;
  category: string;
  image: string;
  price: number;
  nutriScore: number; // 0-100
  ecoScore: number; // 0-100
  co2: number; // kg CO2
  protein: number; // grams per 100g
  calories: number; // kcal per 100g
  sugar: number; // grams per 100g
  fiber: number; // grams per 100g
  distanceKm: number;
  packaging: string;
  organic: boolean;
  local: boolean;
  allergens: string[];
  description: string;
  sources: { name: string; url: string }[];
}

export const products: Product[] = [
  {
    id: "1",
    name: "Regular Strawberry Yogurt",
    brand: "DairyBrand",
    category: "Dairy",
    image: "strawberry yogurt food",
    price: 2.99,
    nutriScore: 45,
    ecoScore: 35,
    co2: 2.8,
    protein: 3.5,
    calories: 120,
    sugar: 15,
    fiber: 0.5,
    distanceKm: 450,
    packaging: "Plastic container",
    organic: false,
    local: false,
    allergens: ["milk"],
    description: "Traditional strawberry yogurt with added sugar. Made from conventionally farmed dairy. High sugar content for enhanced taste.",
    sources: [
      { name: "Nutrition Database", url: "https://example.com/nutrition" },
      { name: "Carbon Trust", url: "https://example.com/carbon" }
    ]
  },
  {
    id: "2",
    name: "Organic Greek Yogurt with Berries",
    brand: "LocalFarm",
    category: "Dairy",
    image: "greek yogurt berries organic",
    price: 3.49,
    nutriScore: 85,
    ecoScore: 88,
    co2: 0.9,
    protein: 10,
    calories: 85,
    sugar: 6,
    fiber: 2,
    distanceKm: 28,
    packaging: "Glass jar (recyclable)",
    organic: true,
    local: true,
    allergens: ["milk"],
    description: "Locally sourced organic Greek yogurt with fresh berries from nearby farms. Higher protein content, lower sugar, and minimal processing. Glass packaging is fully recyclable.",
    sources: [
      { name: "Local Farm Cooperative", url: "https://example.com/localfarm" },
      { name: "Organic Certification Board", url: "https://example.com/organic" },
      { name: "Environmental Impact Assessment", url: "https://example.com/impact" }
    ]
  },
  {
    id: "3",
    name: "White Bread",
    brand: "BreadCo",
    category: "Bakery",
    image: "white bread sliced",
    price: 1.99,
    nutriScore: 40,
    ecoScore: 50,
    co2: 1.2,
    protein: 7,
    calories: 265,
    sugar: 4,
    fiber: 2,
    distanceKm: 320,
    packaging: "Plastic bag",
    organic: false,
    local: false,
    allergens: ["gluten", "wheat"],
    description: "Classic white bread made from refined wheat flour. Processed and enriched with vitamins.",
    sources: [
      { name: "Nutrition Facts Database", url: "https://example.com/nutrition" }
    ]
  },
  {
    id: "4",
    name: "Whole Grain Sourdough",
    brand: "Artisan Bakery",
    category: "Bakery",
    image: "sourdough bread rustic",
    price: 4.49,
    nutriScore: 78,
    ecoScore: 85,
    co2: 0.6,
    protein: 9,
    calories: 240,
    sugar: 1,
    fiber: 6,
    distanceKm: 15,
    packaging: "Paper bag (compostable)",
    organic: true,
    local: true,
    allergens: ["gluten", "wheat"],
    description: "Artisan whole grain sourdough bread baked locally using traditional methods. Higher fiber content and naturally fermented for better digestibility. Made with organic wheat from regional farms.",
    sources: [
      { name: "Artisan Bakery Guild", url: "https://example.com/bakery" },
      { name: "Whole Grain Council", url: "https://example.com/wholegrains" }
    ]
  },
  {
    id: "5",
    name: "Imported Chocolate Bar",
    brand: "ChocoCo",
    category: "Snacks",
    image: "chocolate bar wrapper",
    price: 2.49,
    nutriScore: 25,
    ecoScore: 20,
    co2: 5.5,
    protein: 4,
    calories: 535,
    sugar: 45,
    fiber: 3,
    distanceKm: 8500,
    packaging: "Plastic + foil wrapper",
    organic: false,
    local: false,
    allergens: ["milk", "soy"],
    description: "Mass-produced chocolate bar with high sugar content. Cocoa sourced from overseas plantations with conventional farming practices.",
    sources: [
      { name: "Food Standards Agency", url: "https://example.com/standards" }
    ]
  },
  {
    id: "6",
    name: "Fair Trade Dark Chocolate",
    brand: "EthicalCacao",
    category: "Snacks",
    image: "dark chocolate organic fair trade",
    price: 3.99,
    nutriScore: 68,
    ecoScore: 75,
    co2: 2.1,
    protein: 7,
    calories: 480,
    sugar: 24,
    fiber: 8,
    distanceKm: 6200,
    packaging: "Recyclable cardboard",
    organic: true,
    local: false,
    allergens: ["traces of nuts"],
    description: "Fair trade certified dark chocolate (75% cocoa) made from ethically sourced beans. Higher cocoa content provides more antioxidants and fiber. Supports sustainable farming practices.",
    sources: [
      { name: "Fair Trade Foundation", url: "https://example.com/fairtrade" },
      { name: "Cacao Sustainability Report", url: "https://example.com/cacao" }
    ]
  },
  {
    id: "7",
    name: "Regular Orange Juice",
    brand: "JuiceCorp",
    category: "Beverages",
    image: "orange juice carton",
    price: 3.99,
    nutriScore: 50,
    ecoScore: 42,
    co2: 1.8,
    protein: 1,
    calories: 112,
    sugar: 21,
    fiber: 0.5,
    distanceKm: 2800,
    packaging: "Plastic bottle",
    organic: false,
    local: false,
    allergens: [],
    description: "Concentrated orange juice from overseas oranges. Pasteurized and packaged in plastic bottles.",
    sources: [
      { name: "Beverage Industry Data", url: "https://example.com/beverages" }
    ]
  },
  {
    id: "8",
    name: "Fresh Pressed Local Apple Juice",
    brand: "Orchard Fresh",
    category: "Beverages",
    image: "apple juice fresh pressed glass",
    price: 4.49,
    nutriScore: 72,
    ecoScore: 90,
    co2: 0.4,
    protein: 0.5,
    calories: 95,
    sugar: 18,
    fiber: 1.5,
    distanceKm: 35,
    packaging: "Glass bottle (returnable)",
    organic: true,
    local: true,
    allergens: [],
    description: "Fresh pressed apple juice from local orchards. No added sugar or concentrates. Apples grown within 35km using organic methods. Glass bottles can be returned for reuse.",
    sources: [
      { name: "Local Orchard Association", url: "https://example.com/orchard" },
      { name: "Juice Quality Standards", url: "https://example.com/juice" }
    ]
  },
  {
    id: "9",
    name: "Imported Beef Patties",
    brand: "MeatCo",
    category: "Meat",
    image: "beef burger patties",
    price: 6.99,
    nutriScore: 35,
    ecoScore: 15,
    co2: 15.2,
    protein: 18,
    calories: 332,
    sugar: 0,
    fiber: 0,
    distanceKm: 4500,
    packaging: "Plastic tray + film",
    organic: false,
    local: false,
    allergens: [],
    description: "Frozen beef patties from industrial cattle farming. High carbon footprint due to methane emissions and long-distance transport.",
    sources: [
      { name: "Meat Production Database", url: "https://example.com/meat" },
      { name: "Carbon Footprint Study", url: "https://example.com/footprint" }
    ]
  },
  {
    id: "10",
    name: "Plant-Based Burger Patties",
    brand: "GreenProtein",
    category: "Plant-Based",
    image: "plant based burger patties vegan",
    price: 5.99,
    nutriScore: 75,
    ecoScore: 88,
    co2: 1.3,
    protein: 19,
    calories: 240,
    sugar: 1,
    fiber: 6,
    distanceKm: 180,
    packaging: "Recyclable cardboard",
    organic: true,
    local: false,
    allergens: ["soy", "wheat"],
    description: "Plant-based burger patties made from pea protein, soy, and vegetables. Significantly lower environmental impact with 90% less CO2 emissions than beef. Comparable protein content.",
    sources: [
      { name: "Plant-Based Nutrition Institute", url: "https://example.com/plantbased" },
      { name: "Environmental Comparison Study", url: "https://example.com/comparison" }
    ]
  },
  {
    id: "11",
    name: "Regular Pasta",
    brand: "PastaCo",
    category: "Grains",
    image: "pasta spaghetti dry",
    price: 1.49,
    nutriScore: 55,
    ecoScore: 60,
    co2: 0.9,
    protein: 12,
    calories: 371,
    sugar: 3,
    fiber: 3,
    distanceKm: 850,
    packaging: "Plastic bag",
    organic: false,
    local: false,
    allergens: ["gluten", "wheat"],
    description: "Standard durum wheat pasta. Mass-produced with conventional wheat farming.",
    sources: [
      { name: "Grain Standards Board", url: "https://example.com/grains" }
    ]
  },
  {
    id: "12",
    name: "Organic Whole Wheat Pasta",
    brand: "GrainGoodness",
    category: "Grains",
    image: "whole wheat pasta organic",
    price: 2.49,
    nutriScore: 80,
    ecoScore: 85,
    co2: 0.5,
    protein: 14,
    calories: 348,
    sugar: 2,
    fiber: 7,
    distanceKm: 95,
    packaging: "Cardboard box (recyclable)",
    organic: true,
    local: true,
    allergens: ["gluten", "wheat"],
    description: "Organic whole wheat pasta made from locally grown grains. Higher fiber and protein content. Minimal processing preserves nutrients. Eco-friendly packaging.",
    sources: [
      { name: "Organic Grain Cooperative", url: "https://example.com/organiccoop" },
      { name: "Whole Grain Benefits Study", url: "https://example.com/benefits" }
    ]
  }
];

export const allergensList = [
  "milk",
  "eggs",
  "fish",
  "shellfish",
  "tree nuts",
  "peanuts",
  "wheat",
  "gluten",
  "soy",
  "sesame",
  "traces of nuts"
];
