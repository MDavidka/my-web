from playwright.sync_api import sync_playwright, expect

def verify_mobile_design():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # iPhone X viewport
        context = browser.new_context(viewport={'width': 375, 'height': 812})
        page = context.new_page()

        try:
            # Navigate to the login page
            page.goto("http://localhost:30158/login", timeout=10000)

            # Wait for the main container to be visible
            expect(page.locator("div.flex.flex-col.items-center.justify-center")).to_be_visible(timeout=5000)

            # Take a screenshot
            screenshot_path = "jules-scratch/verification/mobile-login-page.png"
            page.screenshot(path=screenshot_path)

            print(f"Screenshot saved to {screenshot_path}")

        except Exception as e:
            print(f"An error occurred: {e}")
            page.screenshot(path="jules-scratch/verification/mobile-error.png")

        finally:
            browser.close()

if __name__ == "__main__":
    verify_mobile_design()
