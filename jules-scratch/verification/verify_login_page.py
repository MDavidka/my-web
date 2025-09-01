from playwright.sync_api import sync_playwright, expect

def verify_login_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Navigate to the login page
            page.goto("http://localhost:30158/login", timeout=10000)

            # Wait for the main container to be visible
            expect(page.locator(".auth-container")).to_be_visible(timeout=5000)

            # Hover over the button
            button = page.locator("a.btn-discord")
            button.hover()

            # Take a screenshot
            screenshot_path = "jules-scratch/verification/login-page-hover.png"
            page.screenshot(path=screenshot_path)

            print(f"Screenshot saved to {screenshot_path}")

        except Exception as e:
            print(f"An error occurred: {e}")
            page.screenshot(path="jules-scratch/verification/error.png")

        finally:
            browser.close()

if __name__ == "__main__":
    verify_login_page()
