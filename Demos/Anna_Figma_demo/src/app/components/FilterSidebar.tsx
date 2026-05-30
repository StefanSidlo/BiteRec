import { Label } from "./ui/label";
import { Slider } from "./ui/slider";
import { Switch } from "./ui/switch";
import { Checkbox } from "./ui/checkbox";
import { Separator } from "./ui/separator";
import { allergensList } from "../data/products";
import type { FilterState } from "./ProductComparison";

interface FilterSidebarProps {
  filters: FilterState;
  setFilters: (filters: FilterState) => void;
}

export function FilterSidebar({ filters, setFilters }: FilterSidebarProps) {
  const handleAllergenToggle = (allergen: string) => {
    const newAllergens = filters.excludedAllergens.includes(allergen)
      ? filters.excludedAllergens.filter(a => a !== allergen)
      : [...filters.excludedAllergens, allergen];
    
    setFilters({ ...filters, excludedAllergens: newAllergens });
  };

  return (
    <div className="space-y-6">
      {/* Priority Sliders */}
      <div className="space-y-6 mb-6">
        <div>
          <div className="flex justify-between mb-2">
            <Label>Nutritional Priority</Label>
            <span className="text-sm text-gray-600">{filters.nutriWeight}%</span>
          </div>
          <Slider
            value={[filters.nutriWeight]}
            onValueChange={(value) => setFilters({ ...filters, nutriWeight: value[0] })}
            min={0}
            max={100}
            step={5}
            className="mb-2"
          />
          <p className="text-xs text-gray-500">
            How much does nutritional value matter in recommendations?
          </p>
        </div>

        <div>
          <div className="flex justify-between mb-2">
            <Label>Ecological Priority</Label>
            <span className="text-sm text-gray-600">{filters.ecoWeight}%</span>
          </div>
          <Slider
            value={[filters.ecoWeight]}
            onValueChange={(value) => setFilters({ ...filters, ecoWeight: value[0] })}
            min={0}
            max={100}
            step={5}
            className="mb-2"
          />
          <p className="text-xs text-gray-500">
            How much does environmental impact matter in recommendations?
          </p>
        </div>
      </div>

      <Separator className="my-6" />

      {/* Nutritional Filters */}
      <div className="mb-6">
        <h3 className="font-medium mb-4">Nutritional Filters</h3>
        <div className="space-y-4">
          <div>
            <div className="flex justify-between mb-2">
              <Label className="text-sm">Min Protein (g/100g)</Label>
              <span className="text-sm text-gray-600">{filters.minProtein}g</span>
            </div>
            <Slider
              value={[filters.minProtein]}
              onValueChange={(value) => setFilters({ ...filters, minProtein: value[0] })}
              min={0}
              max={30}
              step={1}
            />
          </div>

          <div>
            <div className="flex justify-between mb-2">
              <Label className="text-sm">Max Sugar (g/100g)</Label>
              <span className="text-sm text-gray-600">{filters.maxSugar}g</span>
            </div>
            <Slider
              value={[filters.maxSugar]}
              onValueChange={(value) => setFilters({ ...filters, maxSugar: value[0] })}
              min={0}
              max={50}
              step={1}
            />
          </div>
        </div>
      </div>

      <Separator className="my-6" />

      {/* Ecological Filters */}
      <div className="mb-6">
        <h3 className="font-medium mb-4">Ecological Filters</h3>
        <div className="space-y-4">
          <div>
            <div className="flex justify-between mb-2">
              <Label className="text-sm">Max CO₂ (kg)</Label>
              <span className="text-sm text-gray-600">{filters.maxCo2}kg</span>
            </div>
            <Slider
              value={[filters.maxCo2]}
              onValueChange={(value) => setFilters({ ...filters, maxCo2: value[0] })}
              min={0}
              max={20}
              step={0.5}
            />
          </div>

          <div className="flex items-center justify-between">
            <Label htmlFor="organic" className="text-sm">Organic Only</Label>
            <Switch
              id="organic"
              checked={filters.organicOnly}
              onCheckedChange={(checked) => setFilters({ ...filters, organicOnly: checked })}
            />
          </div>

          <div className="flex items-center justify-between">
            <Label htmlFor="local" className="text-sm">Local Only</Label>
            <Switch
              id="local"
              checked={filters.localOnly}
              onCheckedChange={(checked) => setFilters({ ...filters, localOnly: checked })}
            />
          </div>
        </div>
      </div>

      <Separator className="my-6" />

      {/* Allergen Exclusion */}
      <div>
        <h3 className="font-medium mb-4">Exclude Allergens</h3>
        <div className="space-y-3 max-h-64 overflow-y-auto">
          {allergensList.map((allergen) => (
            <div key={allergen} className="flex items-center space-x-2">
              <Checkbox
                id={allergen}
                checked={filters.excludedAllergens.includes(allergen)}
                onCheckedChange={() => handleAllergenToggle(allergen)}
              />
              <label
                htmlFor={allergen}
                className="text-sm capitalize cursor-pointer"
              >
                {allergen}
              </label>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
