import { useState, useMemo, useEffect } from "react";
import { useParams, useNavigate } from "react-router";
import { ArrowLeft, Info, SlidersHorizontal } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { products, allergensList } from "../data/products";
import { FilterSidebar } from "./FilterSidebar";
import { ComparisonChart } from "./ComparisonChart";
import { Badge } from "./ui/badge";
import { Separator } from "./ui/separator";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "./ui/sheet";
import { TopBar } from "./TopBar";

export interface FilterState {
  nutriWeight: number;
  ecoWeight: number;
  excludedAllergens: string[];
  minProtein: number;
  maxSugar: number;
  maxCo2: number;
  organicOnly: boolean;
  localOnly: boolean;
}

export function ProductComparison() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const [isPersonalizeOpen, setIsPersonalizeOpen] = useState(false);

  const [filters, setFilters] = useState<FilterState>({
    nutriWeight: 50,
    ecoWeight: 50,
    excludedAllergens: [],
    minProtein: 0,
    maxSugar: 100,
    maxCo2: 100,
    organicOnly: false,
    localOnly: false,
  });

  // Save preferences when filters change
  useEffect(() => {
    const userEmail = localStorage.getItem('current_user_email');
    if (userEmail) {
      localStorage.setItem(`user_preferences_${userEmail}`, JSON.stringify(filters));
    }
  }, [filters]);

  const handlePreferencesLoad = (preferences: FilterState) => {
    setFilters(preferences);
  };

  const currentProduct = products.find(p => p.id === productId);

  // Find alternative recommendations
  const recommendations = useMemo(() => {
    if (!currentProduct) return [];

    return products
      .filter(p => {
        // Same category
        if (p.category !== currentProduct.category) return false;
        // Not the same product
        if (p.id === currentProduct.id) return false;
        // Filter by allergens
        if (filters.excludedAllergens.some(allergen => p.allergens.includes(allergen))) return false;
        // Filter by criteria
        if (p.protein < filters.minProtein) return false;
        if (p.sugar > filters.maxSugar) return false;
        if (p.co2 > filters.maxCo2) return false;
        if (filters.organicOnly && !p.organic) return false;
        if (filters.localOnly && !p.local) return false;
        
        return true;
      })
      .map(p => {
        // Calculate recommendation score based on user preferences
        const nutriDiff = (p.nutriScore - currentProduct.nutriScore) / 100;
        const ecoDiff = (p.ecoScore - currentProduct.ecoScore) / 100;
        
        const score = (
          nutriDiff * (filters.nutriWeight / 100) +
          ecoDiff * (filters.ecoWeight / 100)
        );
        
        return { product: p, score };
      })
      .filter(item => item.score > 0) // Only show improvements
      .sort((a, b) => b.score - a.score)
      .slice(0, 3); // Top 3 recommendations
  }, [currentProduct, filters]);

  const topRecommendation = recommendations[0]?.product;

  if (!currentProduct) {
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
      <TopBar onPreferencesLoad={handlePreferencesLoad} />

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <Button
              variant="ghost"
              onClick={() => navigate("/")}
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Scanner
            </Button>

            <Sheet open={isPersonalizeOpen} onOpenChange={setIsPersonalizeOpen}>
              <SheetTrigger asChild>
                <Button variant="outline" className="bg-white">
                  <SlidersHorizontal className="w-4 h-4 mr-2" />
                  Personalize
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto">
                <SheetHeader>
                  <SheetTitle>Personalize Your Options</SheetTitle>
                </SheetHeader>
                <div className="mt-6">
                  <FilterSidebar filters={filters} setFilters={setFilters} />
                </div>
              </SheetContent>
            </Sheet>
          </div>

          <h1 className="text-3xl text-green-800">Product Comparison</h1>
          <p className="text-gray-600 mt-2">
            We found better alternatives based on your preferences
          </p>
        </div>

        <div className="space-y-6">
          {/* Comparison Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Current Product */}
            <Card className="overflow-hidden">
                <div className="bg-gray-100 px-4 py-2">
                  <span className="text-sm font-medium text-gray-700">Your Product</span>
                </div>
                <div className="p-6">
                  <div className="h-48 bg-gray-200 rounded-lg mb-4 overflow-hidden">
                    <img
                      src={`https://source.unsplash.com/400x300/?${currentProduct.image}`}
                      alt={currentProduct.name}
                      className="w-full h-full object-cover"
                    />
                  </div>
                  <h3 className="text-xl mb-1">{currentProduct.name}</h3>
                  <p className="text-sm text-gray-600 mb-2">{currentProduct.brand}</p>
                  <p className="text-2xl text-green-700 mb-4">${currentProduct.price}</p>
                  
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Nutri-Score:</span>
                      <span className="font-medium">{currentProduct.nutriScore}/100</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Eco-Score:</span>
                      <span className="font-medium">{currentProduct.ecoScore}/100</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">CO₂ Footprint:</span>
                      <span className="font-medium">{currentProduct.co2} kg</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Distance:</span>
                      <span className="font-medium">{currentProduct.distanceKm} km</span>
                    </div>
                  </div>

                  <Button
                    variant="outline"
                    className="w-full mt-4"
                    onClick={() => navigate(`/product/${currentProduct.id}`)}
                  >
                    <Info className="w-4 h-4 mr-2" />
                    View Details
                  </Button>
                </div>
              </Card>

            {/* Recommended Alternative */}
            {topRecommendation ? (
                <Card className="overflow-hidden border-2 border-green-500">
                  <div className="bg-green-500 px-4 py-2">
                    <span className="text-sm font-medium text-white">Recommended Alternative</span>
                  </div>
                  <div className="p-6">
                    <div className="h-48 bg-gray-200 rounded-lg mb-4 overflow-hidden">
                      <img
                        src={`https://source.unsplash.com/400x300/?${topRecommendation.image}`}
                        alt={topRecommendation.name}
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <h3 className="text-xl mb-1">{topRecommendation.name}</h3>
                    <p className="text-sm text-gray-600 mb-2">{topRecommendation.brand}</p>
                    <p className="text-2xl text-green-700 mb-4">${topRecommendation.price}</p>
                    
                    <div className="space-y-2 text-sm mb-4">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Nutri-Score:</span>
                        <span className="font-medium text-green-600">
                          {topRecommendation.nutriScore}/100
                          {topRecommendation.nutriScore > currentProduct.nutriScore && (
                            <span className="ml-1">↑</span>
                          )}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Eco-Score:</span>
                        <span className="font-medium text-green-600">
                          {topRecommendation.ecoScore}/100
                          {topRecommendation.ecoScore > currentProduct.ecoScore && (
                            <span className="ml-1">↑</span>
                          )}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">CO₂ Footprint:</span>
                        <span className="font-medium text-green-600">
                          {topRecommendation.co2} kg
                          {topRecommendation.co2 < currentProduct.co2 && (
                            <span className="ml-1">↓</span>
                          )}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Distance:</span>
                        <span className="font-medium text-green-600">
                          {topRecommendation.distanceKm} km
                          {topRecommendation.distanceKm < currentProduct.distanceKm && (
                            <span className="ml-1">↓</span>
                          )}
                        </span>
                      </div>
                    </div>

                    {topRecommendation.local && (
                      <div className="mb-4">
                        <Badge className="bg-green-100 text-green-800">
                          Grown {topRecommendation.distanceKm} km away
                        </Badge>
                      </div>
                    )}

                    <Button
                      variant="default"
                      className="w-full bg-green-600 hover:bg-green-700"
                      onClick={() => navigate(`/product/${topRecommendation.id}`)}
                    >
                      <Info className="w-4 h-4 mr-2" />
                      View Details
                    </Button>
                  </div>
                </Card>
            ) : (
              <Card className="overflow-hidden border-2 border-gray-300">
                <div className="p-6 text-center">
                  <h3 className="text-xl mb-2">No Alternatives Found</h3>
                  <p className="text-gray-600 mb-4">
                    Try adjusting your filters to see more options
                  </p>
                </div>
              </Card>
            )}
          </div>

          {/* Comparison Chart */}
          {topRecommendation && (
            <Card className="p-6">
              <h3 className="text-xl mb-6">Detailed Comparison</h3>
              <ComparisonChart
                currentProduct={currentProduct}
                recommendedProduct={topRecommendation}
              />
            </Card>
          )}

          {/* Additional Recommendations */}
          {recommendations.length > 1 && (
            <Card className="p-6">
              <h3 className="text-xl mb-4">Other Alternatives</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {recommendations.slice(1).map(({ product: rec }) => (
                  <div
                    key={rec.id}
                    className="flex gap-4 p-4 border rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/product/${rec.id}`)}
                  >
                    <div className="w-24 h-24 bg-gray-200 rounded overflow-hidden flex-shrink-0">
                      <img
                        src={`https://source.unsplash.com/150x150/?${rec.image}`}
                        alt={rec.name}
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-medium mb-1">{rec.name}</h4>
                      <p className="text-sm text-gray-600 mb-2">{rec.brand}</p>
                      <div className="flex gap-2 text-xs">
                        <Badge variant="outline" className="bg-green-50">
                          Nutri: {rec.nutriScore}
                        </Badge>
                        <Badge variant="outline" className="bg-blue-50">
                          Eco: {rec.ecoScore}
                        </Badge>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-medium text-green-700">${rec.price}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
