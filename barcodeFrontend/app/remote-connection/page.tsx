"use client";

import { ScrollButtons } from '@/components/ui/ScrollButtons';

export default function RemoteConnectionPage() {
  return (
    <div className="min-h-screen bg-[var(--background)] text-[var(--foreground)] p-4 md:p-8">
      <header className="text-center mb-12 md:mb-16 animate-fadeInDown">
        <h1 className="text-4xl md:text-5xl font-extrabold mb-4 tracking-tight text-[var(--accent-color)]">
          Remote Connection Guide
        </h1>
        <p className="text-lg md:text-xl text-slate-500 dark:text-slate-400">
          Connect to the MCP server with theBarcodeAPI
        </p>
      </header>

      <main className="max-w-5xl mx-auto space-y-12 md:space-y-16">
        <section className="bg-[var(--light-bg)] p-6 md:p-8 rounded-xl shadow-lg animate-fadeInUp animation-delay-200">
          <h2 className="text-2xl md:text-3xl font-semibold mb-6 border-b-2 border-[var(--accent-color)] pb-3 text-[var(--accent-color)]/90">
            Introduction
          </h2>
          <p className="text-md md:text-lg leading-relaxed mb-4">
            The Multi-purpose Communication Platform (MCP) server is the backbone of theBarcodeAPI.com, providing robust and scalable services for various AI-powered tasks, including barcode generation and scanning. Users might want to connect to it remotely to integrate these functionalities directly into their own applications, automate processes, or build custom solutions.
          </p>
          <p className="text-md md:text-lg leading-relaxed">
            Using `thebarcodeapi.com` for remote connections offers several benefits:
          </p>
          <ul className="list-disc list-inside mt-4 space-y-2 text-md md:text-lg">
            <li><strong>Simplified Integration:</strong> Access powerful barcode functionalities through a simple HTTP API.</li>
            <li><strong>Scalability:</strong> Rely on our robust infrastructure to handle your requests, from small projects to enterprise-level applications.</li>
            <li><strong>Cross-Platform Compatibility:</strong> Connect from any platform or programming language that supports HTTP requests.</li>
            <li><strong>Focus on Your Core Logic:</strong> Offload complex barcode processing to our specialized servers and focus on your application&apos;s unique features.</li>
          </ul>
        </section>

        <section className="bg-[var(--light-bg)] p-6 md:p-8 rounded-xl shadow-lg animate-fadeInUp animation-delay-400">
          <h2 className="text-2xl md:text-3xl font-semibold mb-6 border-b-2 border-[var(--accent-color)] pb-3 text-[var(--accent-color)]/90">
            Connecting with C# (Visual Studio)
          </h2>
          <p className="text-md md:text-lg leading-relaxed mb-6">
            This section provides a step-by-step guide to connect to `thebarcodeapi.com` using C# in Visual Studio. We&apos;ll demonstrate how to make a POST request to generate a barcode.
          </p>
          
          <h3 className="text-xl md:text-2xl font-medium mb-4 text-[var(--accent-color)]/80">Prerequisites</h3>
          <ul className="list-disc list-inside mb-6 space-y-1">
            <li>.NET Core SDK or .NET Framework (typically included with Visual Studio).</li>
            <li>Visual Studio IDE.</li>
            <li>A basic understanding of C# and asynchronous programming.</li>
            <li>For older .NET Framework versions, you might need to install `Newtonsoft.Json` via NuGet for JSON handling. For .NET Core and .NET 5+, `System.Text.Json` is built-in. We will use `System.Net.Http.Json` for simplicity in this example, which is available in modern .NET versions.</li>
            <li>Your API Key from theBarcodeAPI.com (replace &quot;YOUR_API_KEY&quot; in the code).</li>
          </ul>

          <h3 className="text-xl md:text-2xl font-medium mb-4 text-[var(--accent-color)]/80">Step-by-Step Guide</h3>
          <ol className="list-decimal list-inside space-y-3 mb-6">
            <li><strong>Create a new Project:</strong> Open Visual Studio and create a new Console App (.NET Core or .NET).</li>
            <li><strong>Write the Code:</strong> Copy and paste the C# code snippet below into your `Program.cs` file.</li>
            <li><strong>Replace API Key:</strong> Update the `apiKey` variable with your actual API key.</li>
            <li><strong>Run the Application:</strong> Execute the code. It will make a POST request to the barcode generation endpoint and print the response (which could be an image URL or binary data depending on the API).</li>
          </ol>

          <div className="mt-6 bg-black/20 dark:bg-black/30 p-4 md:p-6 rounded-lg shadow-inner border border-white/10 dark:border-white/5">
            <h3 className="text-lg md:text-xl font-semibold mb-3 text-[var(--accent-color)]/70">C# Code Example</h3>
            <pre className="bg-transparent p-3 md:p-4 rounded-md overflow-x-auto text-sm md:text-base">
              <code className="language-csharp text-slate-300 dark:text-slate-200">
                {`using System;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json; // Requires .NET 5+ or System.Net.Http.Json NuGet package
using System.Text;
using System.Text.Json; // For older .NET, use Newtonsoft.Json
using System.Threading.Tasks;

public class BarcodeGenerator
{
    private static readonly HttpClient client = new HttpClient();

    public static async Task Main(string[] args)
    {
        string apiKey = "YOUR_API_KEY"; // Replace with your actual API key
        string apiUrl = "https://api.thebarcodeapi.com/api/barcode/generate";

        var payload = new
        {
            text = "Hello from C#",
            format = "qrcode", // e.g., qrcode, code128, ean13
            scale = 3,
            rotate = "N", // N, R, L
            background = "#ffffff",
            foreground = "#000000"
        };

        try
        {
            client.DefaultRequestHeaders.Clear();
            client.DefaultRequestHeaders.Add("X-API-Key", apiKey);
            client.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json")); // Or "image/png" if you expect direct image

            // For .NET Core 3.1 and older, or .NET Framework without System.Net.Http.Json:
            // string jsonPayload = JsonSerializer.Serialize(payload);
            // HttpContent content = new StringContent(jsonPayload, Encoding.UTF8, "application/json");
            // HttpResponseMessage response = await client.PostAsync(apiUrl, content);

            // For .NET 5+ with System.Net.Http.Json:
            HttpResponseMessage response = await client.PostAsJsonAsync(apiUrl, payload);

            response.EnsureSuccessStatusCode();

            Console.WriteLine("API Request Successful!");
            
            // Option 1: Get image URL if API returns JSON with URL
            // string responseBody = await response.Content.ReadAsStringAsync();
            // Console.WriteLine("Response JSON: " + responseBody);
            // // Assuming JSON response: {"imageUrl": "...", "format": "..."}
            // // var result = JsonSerializer.Deserialize<Dictionary<string, string>>(responseBody);
            // // Console.WriteLine("Barcode Image URL: " + result["imageUrl"]);

            // Option 2: Save direct image stream (if API returns image/*)
            // Ensure your 'Accept' header is 'image/png' or similar
            if (response.Content.Headers.ContentType?.MediaType?.StartsWith("image/") == true)
            {
                var imageBytes = await response.Content.ReadAsByteArrayAsync();
                string fileName = $"barcode_{payload.format}.png"; // or jpg, etc.
                System.IO.File.WriteAllBytes(fileName, imageBytes);
                Console.WriteLine($"Barcode image saved as {fileName}");
            }
            else
            {
                 // Default: assume JSON response with details or error
                string responseBody = await response.Content.ReadAsStringAsync();
                Console.WriteLine("Response Body: " + responseBody);
            }
        }
        catch (HttpRequestException e)
        {
            Console.WriteLine($"Request error: {e.Message}");
            if (e.StatusCode.HasValue)
            {
                Console.WriteLine($"Status Code: {e.StatusCode.Value}");
            }
            // Optionally read error response body
            // if (e.HttpRequestError == HttpRequestError.BadResponse && e.Response != null)
            // {
            //     string errorContent = await e.Response.Content.ReadAsStringAsync();
            //     Console.WriteLine($"Error Content: {errorContent}");
            // }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"An unexpected error occurred: {ex.Message}");
        }
    }
}`}
              </code>
            </pre>
            <p className="mt-4 text-xs md:text-sm text-slate-400 dark:text-slate-500">
              Remember to replace &quot;YOUR_API_KEY&quot; with your actual key. The code includes options for handling JSON responses (e.g., an image URL) or direct image data. Adjust the `Accept` header and response processing accordingly.
            </p>
          </div>
        </section>

        <section className="bg-[var(--light-bg)] p-6 md:p-8 rounded-xl shadow-lg animate-fadeInUp animation-delay-600">
          <h2 className="text-2xl md:text-3xl font-semibold mb-6 border-b-2 border-[var(--accent-color)] pb-3 text-[var(--accent-color)]/90">
            Connecting with Python
          </h2>
          <p className="text-md md:text-lg leading-relaxed mb-6">
            This section demonstrates how to connect to `thebarcodeapi.com` using a Python script. We&apos;ll use the popular `requests` library to make a POST request for barcode generation.
          </p>

          <h3 className="text-xl md:text-2xl font-medium mb-4 text-[var(--accent-color)]/80">Prerequisites</h3>
          <ul className="list-disc list-inside mb-6 space-y-1">
            <li>Python 3.6+ installed.</li>
            <li>The `requests` library. You can install it using pip: <code className="bg-black/20 dark:bg-black/30 p-1 rounded text-xs text-[var(--accent-color)]">pip install requests</code>.</li>
            <li>Your API Key from theBarcodeAPI.com (replace &quot;YOUR_API_KEY&quot; in the code).</li>
          </ul>

          <h3 className="text-xl md:text-2xl font-medium mb-4 text-[var(--accent-color)]/80">Step-by-Step Guide</h3>
          <ol className="list-decimal list-inside space-y-3 mb-6">
            <li><strong>Install `requests`:</strong> If you haven&apos;t already, open your terminal or command prompt and run `pip install requests`.</li>
            <li><strong>Create a Python file:</strong> Create a new file (e.g., `barcode_request.py`).</li>
            <li><strong>Write the Code:</strong> Copy and paste the Python code snippet below into your file.</li>
            <li><strong>Replace API Key:</strong> Update the `api_key` variable with your actual API key.</li>
            <li><strong>Run the Script:</strong> Execute the script from your terminal: `python barcode_request.py`. It will send the request and print the server&apos;s response.</li>
          </ol>
          
          <div className="mt-6 bg-black/20 dark:bg-black/30 p-4 md:p-6 rounded-lg shadow-inner border border-white/10 dark:border-white/5">
            <h3 className="text-lg md:text-xl font-semibold mb-3 text-[var(--accent-color)]/70">Python Code Example</h3>
            <pre className="bg-transparent p-3 md:p-4 rounded-md overflow-x-auto text-sm md:text-base">
              <code className="language-python text-slate-300 dark:text-slate-200">
                {`import requests
import json

def generate_barcode():
    api_key = "YOUR_API_KEY"  # Replace with your actual API key
    api_url = "https://api.thebarcodeapi.com/api/barcode/generate"

    headers = {
        "X-API-Key": api_key,
        "Content-Type": "application/json",
        # "Accept": "image/png" # Uncomment if you want to receive the image directly
        "Accept": "application/json" # Default: expect a JSON response
    }

    payload = {
        "text": "Hello from Python",
        "format": "qrcode",  # e.g., qrcode, code128, datamatrix
        "scale": 3,
        "rotate": "N",  # N, R, L
        "background": "#ffffff",
        "foreground": "#000000"
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)

        print("API Request Successful!")

        # Option 1: Handle JSON response (e.g., if API returns image URL)
        if "application/json" in response.headers.get("Content-Type", ""):
            data = response.json()
            print("Response JSON:", json.dumps(data, indent=2))
            # if "imageUrl" in data:
            #     print(f"Barcode Image URL: {data['imageUrl']}")
            #     # You can then download the image using data['imageUrl']
            #     # image_response = requests.get(data['imageUrl'])
            #     # with open(f"barcode_from_url.{data.get('format', 'png')}", "wb") as f:
            #     #     f.write(image_response.content)
            #     # print(f"Barcode saved as barcode_from_url.{data.get('format', 'png')}")

        # Option 2: Handle direct image response
        elif response.headers.get("Content-Type", "").startswith("image/"):
            image_format = response.headers.get("Content-Type").split("/")[-1]
            file_name = f"barcode.{image_format}"
            with open(file_name, "wb") as f:
                f.write(response.content)
            print(f"Barcode image saved as {file_name}")
        
        else:
            print(f"Unexpected content type: {response.headers.get('Content-Type')}")
            print("Raw response:", response.text)


    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Response content: {response.content.decode()}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request error occurred: {req_err}")
    except Exception as ex:
        print(f"An unexpected error occurred: {ex}")

if __name__ == "__main__":
    generate_barcode()`}
              </code>
            </pre>
            <p className="mt-4 text-xs md:text-sm text-slate-400 dark:text-slate-500">
              Ensure you replace &quot;YOUR_API_KEY&quot;. This script currently expects a JSON response. If the API is configured to send the image directly, you&apos;ll need to adjust the `Accept` header to something like &quot;image/png&quot; and modify the response handling to save `response.content` to a file.
            </p>
          </div>
        </section>

        <section className="text-center mt-12 md:mt-16 animate-fadeInUp animation-delay-800">
          <p className="text-slate-500 dark:text-slate-400">
            For more advanced features or other programming languages, please refer to our full API documentation.
          </p>
        </section>
      </main>

      <style jsx global>{`
        /* Ensure body takes full height and uses global font */
        body {
          min-height: 100vh;
          font-family: var(--font-geist-sans), system-ui, sans-serif;
        }
        /* Custom animation delays */
        .animation-delay-200 { animation-delay: 0.2s; }
        .animation-delay-400 { animation-delay: 0.4s; }
        .animation-delay-600 { animation-delay: 0.6s; }
        .animation-delay-800 { animation-delay: 0.8s; }

        /* FadeInDown Animation */
        @keyframes fadeInDown {
          from {
            opacity: 0;
            transform: translateY(-25px); /* Slightly increased distance */
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fadeInDown {
          animation: fadeInDown 0.6s ease-out forwards; /* Slightly longer duration */
        }

        /* FadeInUp Animation */
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(25px); /* Slightly increased distance */
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fadeInUp {
          animation: fadeInUp 0.6s ease-out forwards; /* Slightly longer duration */
          opacity: 0; /* Ensure it starts hidden for the animation to take effect */
        }

        /* Improve focus visibility for accessibility on interactive elements */
        *:focus-visible {
          outline: 2px solid var(--accent-color);
          outline-offset: 2px;
        }
        
        /* Code block specific styling for syntax highlighting (conceptual) */
        /* You would typically use a library like Prism.js or Highlight.js that adds its own classes */
        code[class*="language-"] {
          font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
          line-height: 1.6; /* Improved line spacing for code */
        }
        .token.comment,
        .token.prolog,
        .token.doctype,
        .token.cdata {
          color: #9ca3af; /* gray-400 / gray-500 */
        }
        .token.punctuation {
          color: #e5e7eb; /* gray-200 */
        }
        .token.property,
        .token.tag,
        .token.boolean,
        .token.number,
        .token.constant,
        .token.symbol,
        .token.deleted {
          color: #f08080; /* LightCoral */
        }
        .token.selector,
        .token.attr-name,
        .token.string,
        .token.char,
        .token.builtin,
        .token.inserted {
          color: #a7f3d0; /* emerald-200 */
        }
        .token.operator,
        .token.entity,
        .token.url,
        .language-css .token.string,
        .style .token.string {
          color: #c792ea; /* Softer purple */
        }
        .token.atrule,
        .token.attr-value,
        .token.keyword {
          color: #89ddff; /* sky-300 */
        }
        .token.function,
        .token.class-name {
          color: #fde047; /* yellow-300 */
        }
        .token.regex,
        .token.important,
        .token.variable {
          color: #fda4af; /* rose-300 */
        }

      `}</style>
      <ScrollButtons />
    </div>
  );
}
