import { useState } from "react";
import { useNavigate } from "react-router";
import { Camera, Search } from "lucide-react";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";
import { products } from "../data/products";
import { TopBar } from "./TopBar";

export function ProductScanner() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState("");
  const [isScanning, setIsScanning] = useState(false);

  const filteredProducts = products.filter(p =>
    p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.brand.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.category.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleScan = () => {
    setIsScanning(true);
    // Simulate scanning - randomly select a product after a delay
    setTimeout(() => {
      const randomProduct = products[Math.floor(Math.random() * products.length)];
      setIsScanning(false);
      navigate(`/compare/${randomProduct.id}`);
    }, 2000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-50 to-white">
      <TopBar />

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl mb-4 text-green-800">EcoChoice</h1>
          <p className="text-xl text-gray-600">
            Scan products to find healthier and more eco-friendly alternatives
          </p>
        </div>

        {/* Scanner Section */}
        <Card className="max-w-2xl mx-auto mb-12 p-8">
          <div className="text-center">
            <div className="mb-6">
              <div className={`inline-flex items-center justify-center w-32 h-32 rounded-full ${isScanning ? 'bg-green-200 animate-pulse' : 'bg-green-100'} mb-4`}>
                <Camera className={`w-16 h-16 text-green-700 ${isScanning ? 'animate-bounce' : ''}`} />
              </div>
            </div>
            
            <h2 className="text-2xl mb-4">Scan a Product</h2>
            <p className="text-gray-600 mb-6">
              {isScanning ? 'Analyzing product...' : 'Click to simulate scanning a product barcode'}
            </p>
            
            <Button 
              onClick={handleScan}
              disabled={isScanning}
              size="lg"
              className="bg-green-600 hover:bg-green-700"
            >
              {isScanning ? 'Scanning...' : 'Start Scan'}
            </Button>
          </div>
        </Card>

        {/* Search Section */}
        <div className="max-w-2xl mx-auto mb-8">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
            <Input
              type="text"
              placeholder="Or search for products manually..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>

        {/* Product Grid */}
        {searchTerm && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredProducts.map((product) => (
              <Card
                key={product.id}
                className="overflow-hidden hover:shadow-lg transition-shadow cursor-pointer"
                onClick={() => navigate(`/compare/${product.id}`)}
              >
                <div className="h-48 bg-gray-200 relative overflow-hidden">
                  <img
                    src={`https://source.unsplash.com/400x300/?${product.image}`}
                    alt={product.name}
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <h3 className="font-semibold text-lg">{product.name}</h3>
                      <p className="text-sm text-gray-600">{product.brand}</p>
                    </div>
                    <span className="text-lg">${product.price}</span>
                  </div>
                  
                  <div className="flex gap-2 mt-3">
                    <div className="flex-1">
                      <div className="text-xs text-gray-600 mb-1">Nutri-Score</div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-green-500 h-2 rounded-full"
                          style={{ width: `${product.nutriScore}%` }}
                        />
                      </div>
                    </div>
                    <div className="flex-1">
                      <div className="text-xs text-gray-600 mb-1">Eco-Score</div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full"
                          style={{ width: `${product.ecoScore}%` }}
                        />
                      </div>
                    </div>
                  </div>

                  {product.local && (
                    <div className="mt-3 text-xs text-green-700 bg-green-50 px-2 py-1 rounded inline-block">
                      Grown {product.distanceKm} km away
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}

        {searchTerm && filteredProducts.length === 0 && (
          <div className="text-center text-gray-500 py-12">
            No products found matching "{searchTerm}"
          </div>
        )}
      </div>
    </div>
  );
}
