import { useParams, useNavigate } from "react-router";
import { ArrowLeft, ExternalLink, Leaf, MapPin, Package, Award } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Separator } from "./ui/separator";
import { Progress } from "./ui/progress";
import { products } from "../data/products";
import { TopBar } from "./TopBar";

export function ProductDetail() {
  const { productId } = useParams();
  const navigate = useNavigate();
  
  const product = products.find(p => p.id === productId);

  if (!product) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl mb-4">Product not found</h2>
          <Button onClick={() => navigate("/")}>Back to Scanner</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <TopBar />

      <div className="max-w-5xl mx-auto px-4 py-6">
        {/* Header */}
        <Button
          variant="ghost"
          onClick={() => navigate(-1)}
          className="mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
          {/* Product Image */}
          <Card className="overflow-hidden">
            <div className="aspect-square bg-gray-200">
              <img
                src={`https://source.unsplash.com/600x600/?${product.image}`}
                alt={product.name}
                className="w-full h-full object-cover"
              />
            </div>
          </Card>

          {/* Product Info */}
          <div>
            <h1 className="text-3xl mb-2">{product.name}</h1>
            <p className="text-xl text-gray-600 mb-4">{product.brand}</p>
            <p className="text-3xl text-green-700 mb-6">${product.price}</p>

            {/* Badges */}
            <div className="flex flex-wrap gap-2 mb-6">
              {product.organic && (
                <Badge className="bg-green-100 text-green-800 flex items-center gap-1">
                  <Leaf className="w-3 h-3" />
                  Organic
                </Badge>
              )}
              {product.local && (
                <Badge className="bg-blue-100 text-blue-800 flex items-center gap-1">
                  <MapPin className="w-3 h-3" />
                  Local
                </Badge>
              )}
              <Badge variant="outline">{product.category}</Badge>
            </div>

            {/* Description */}
            <p className="text-gray-700 mb-6 leading-relaxed">{product.description}</p>

            {/* Quick Scores */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              <Card className="p-4">
                <div className="text-sm text-gray-600 mb-2">Nutritional Score</div>
                <div className="text-2xl font-medium mb-2">{product.nutriScore}/100</div>
                <Progress value={product.nutriScore} className="h-2" />
              </Card>
              <Card className="p-4">
                <div className="text-sm text-gray-600 mb-2">Ecological Score</div>
                <div className="text-2xl font-medium mb-2">{product.ecoScore}/100</div>
                <Progress value={product.ecoScore} className="h-2" />
              </Card>
            </div>
          </div>
        </div>

        {/* Detailed Information */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* Nutritional Information */}
          <Card className="p-6">
            <h2 className="text-xl mb-4 flex items-center gap-2">
              <Award className="w-5 h-5 text-green-600" />
              Nutritional Information
            </h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Calories (per 100g)</span>
                <span className="font-medium">{product.calories} kcal</span>
              </div>
              <Separator />
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Protein</span>
                <span className="font-medium">{product.protein}g</span>
              </div>
              <Separator />
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Sugar</span>
                <span className="font-medium">{product.sugar}g</span>
              </div>
              <Separator />
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Fiber</span>
                <span className="font-medium">{product.fiber}g</span>
              </div>
              <Separator />
              <div className="flex justify-between items-center">
                <span className="text-gray-600">Allergens</span>
                <span className="font-medium capitalize">
                  {product.allergens.length > 0 ? product.allergens.join(", ") : "None"}
                </span>
              </div>
            </div>
          </Card>

          {/* Environmental Impact */}
          <Card className="p-6">
            <h2 className="text-xl mb-4 flex items-center gap-2">
              <Leaf className="w-5 h-5 text-green-600" />
              Environmental Impact
            </h2>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-gray-600">Carbon Footprint</span>
                  <span className="font-medium">{product.co2} kg CO₂</span>
                </div>
                <div className="text-xs text-gray-500">
                  {product.co2 < 1 
                    ? "Very low carbon footprint" 
                    : product.co2 < 3 
                    ? "Low carbon footprint" 
                    : product.co2 < 10
                    ? "Moderate carbon footprint"
                    : "High carbon footprint"}
                </div>
              </div>
              <Separator />
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-gray-600">Transportation Distance</span>
                  <span className="font-medium">{product.distanceKm} km</span>
                </div>
                <div className="text-xs text-gray-500">
                  {product.local ? (
                    <span className="text-green-600 font-medium">
                      Grown {product.distanceKm} km away - supports local economy
                    </span>
                  ) : (
                    "Imported from afar"
                  )}
                </div>
              </div>
              <Separator />
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-gray-600">Packaging</span>
                  <span className="font-medium">{product.packaging}</span>
                </div>
                <div className="text-xs text-gray-500">
                  {product.packaging.toLowerCase().includes("recyclable") || 
                   product.packaging.toLowerCase().includes("compostable") || 
                   product.packaging.toLowerCase().includes("glass") || 
                   product.packaging.toLowerCase().includes("cardboard")
                    ? "Eco-friendly packaging"
                    : "Consider recycling options"}
                </div>
              </div>
              <Separator />
              <div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Production Method</span>
                  <span className="font-medium">{product.organic ? "Organic" : "Conventional"}</span>
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Sources */}
        <Card className="p-6">
          <h2 className="text-xl mb-4 flex items-center gap-2">
            <ExternalLink className="w-5 h-5 text-green-600" />
            Information Sources
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            All data has been compiled from verified sources. Click to learn more:
          </p>
          <div className="space-y-2">
            {product.sources.map((source, index) => (
              <a
                key={index}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors group"
              >
                <ExternalLink className="w-4 h-4 text-gray-400 group-hover:text-green-600" />
                <span className="text-gray-700 group-hover:text-green-700">{source.name}</span>
              </a>
            ))}
          </div>
          <div className="mt-4 p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-gray-700">
              <strong>Note:</strong> These are example URLs for demonstration purposes. 
              In a real application, these would link to actual databases and certification bodies.
            </p>
          </div>
        </Card>

        {/* Compare Button */}
        <div className="mt-8 text-center">
          <Button
            onClick={() => navigate(`/compare/${product.id}`)}
            size="lg"
            className="bg-green-600 hover:bg-green-700"
          >
            Find Better Alternatives
          </Button>
        </div>
      </div>
    </div>
  );
}
