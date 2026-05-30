import { useState, useEffect } from "react";
import { User, LogOut } from "lucide-react";
import { Button } from "./ui/button";
import { LoginDialog } from "./LoginDialog";

interface TopBarProps {
  onPreferencesLoad?: (preferences: any) => void;
}

export function TopBar({ onPreferencesLoad }: TopBarProps) {
  const [user, setUser] = useState<{ name: string; email: string } | null>(null);
  const [showLoginDialog, setShowLoginDialog] = useState(false);

  // Check for existing session on mount
  useEffect(() => {
    const currentUserEmail = localStorage.getItem('current_user_email');
    if (currentUserEmail) {
      const userData = {
        name: currentUserEmail.split('@')[0],
        email: currentUserEmail,
      };
      setUser(userData);

      // Load preferences on mount if user is logged in
      const savedPreferences = localStorage.getItem(`user_preferences_${currentUserEmail}`);
      if (savedPreferences && onPreferencesLoad) {
        const preferences = JSON.parse(savedPreferences);
        onPreferencesLoad(preferences);
      }
    }
  }, [onPreferencesLoad]);

  const handleLogin = (email: string, password: string) => {
    // Simulate login - in real app, this would call an API
    // For demo, we'll use localStorage to store/retrieve user preferences
    const savedPreferences = localStorage.getItem(`user_preferences_${email}`);

    const userData = {
      name: email.split('@')[0],
      email: email,
    };

    setUser(userData);
    setShowLoginDialog(false);

    // Store current user email for auto-saving preferences
    localStorage.setItem('current_user_email', email);

    // Load saved preferences if they exist
    if (savedPreferences && onPreferencesLoad) {
      const preferences = JSON.parse(savedPreferences);
      onPreferencesLoad(preferences);
    }
  };

  const handleLogout = () => {
    setUser(null);
    localStorage.removeItem('current_user_email');
  };

  return (
    <>
      <div className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-green-600 rounded-full flex items-center justify-center">
              <span className="text-white font-bold text-sm">EC</span>
            </div>
            <h1 className="text-xl font-semibold text-green-800">EcoChoice</h1>
          </div>

          <div className="flex items-center gap-3">
            {user ? (
              <>
                <div className="text-sm text-gray-600">
                  Welcome, <span className="font-medium">{user.name}</span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleLogout}
                >
                  <LogOut className="w-4 h-4 mr-2" />
                  Logout
                </Button>
              </>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowLoginDialog(true)}
              >
                <User className="w-4 h-4 mr-2" />
                Login
              </Button>
            )}
          </div>
        </div>
      </div>

      <LoginDialog
        open={showLoginDialog}
        onClose={() => setShowLoginDialog(false)}
        onLogin={handleLogin}
      />
    </>
  );
}
