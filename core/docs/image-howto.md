# Nano-GPT Image Generation API Reference

This document outlines how to use the `nano-gpt.com` image generation API for PenCMS. 

Nano-GPT provides two endpoints for generating images:
1. **Plan A (Recommended): Dedicated Image API (`/api/v1/images`)** - This is the preferred method for new integrations because it natively supports modern features like model discovery, endpoint pricing metadata, and advanced parameters (like custom aspect ratios, negative prompts, and schedulers) which do not fit cleanly into the OpenAI schema.
2. **Plan B (Fallback): OpenAI-Compatible Endpoint (`/v1/images/generations`)** - This is the legacy method currently used by the MasterGrade extension. We keep this documented as a proven fallback in case the new method has unforeseen issues.

---

## PLAN A: Dedicated Image API (Recommended)

*   **Endpoint:** `https://nano-gpt.com/api/v1/images`
*   **Method:** `POST`

### Headers

*   `Authorization: Bearer <YOUR_API_KEY>`
*   `Content-Type: application/json`

### Request Body (JSON)

The dedicated API uses a flexible schema capable of handling advanced parameters specific to models like Flux or Stable Diffusion.

```json
{
  "prompt": "Your descriptive prompt goes here...",
  "model": "qwen-image",
  "width": 1024,
  "height": 1024,
  "negative_prompt": "ugly, blurry, deformed",
  "response_format": "b64_json"
}
```

*   **`response_format`**: Set to `"b64_json"` so you receive base64-encoded strings directly instead of ephemeral URLs, allowing PenCMS to save them locally.
*   *Note: Check the `/api/v1/images/models` endpoint programmatically to see exact parameter support (like steps, sampler, or CFG scale) for each specific model.*

### Integrating into PenCMS
1. Use the dedicated endpoint.
2. When PenCMS receives the `b64_json` value in the response, base64-decode the string and write the raw binary data to a `.png` or `.jpg` file in the media directory.
3. Return the local URL for the frontend.

---

## PLAN B: OpenAI-Compatible Endpoint (Fallback / Legacy)

This is the exact implementation currently proven to work in the MasterGrade extension.

*   **Endpoint:** `https://nano-gpt.com/v1/images/generations`
*   **Method:** `POST`

### Headers

*   `Authorization: Bearer <YOUR_API_KEY>`
*   `Content-Type: application/json`

### Request Body (JSON)

This payload forces parameters into the rigid OpenAI structure:

```json
{
  "model": "qwen-image",
  "prompt": "Your descriptive prompt goes here...",
  "n": 1,
  "size": "1024x1024",
  "response_format": "b64_json"
}
```

### Response Handling (Extension Reference)

A successful request returns a JSON object. Here is how the extension processes it:

```javascript
const response = await fetch('https://nano-gpt.com/v1/images/generations', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
});

if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.error?.message || `API Error: ${response.status}`);
}

const result = await response.json();

const b64 = result.data?.[0]?.b64_json;
const url = result.data?.[0]?.url;

if (b64) {
    // Return Base64 data URI format, ready for an <img> tag or to be written to a file
    const imageDataUri = `data:image/png;base64,${b64}`;
    // In PenCMS, you would decode this base64 string and save it to the local filesystem
} else if (url) {
    // Fallback if the API returns a URL instead of base64
    const imageUrl = url; 
}
```
