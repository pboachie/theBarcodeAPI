// barcodeService.ts

const apiDomain = process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : 'https://thebarcodeapi.com';

export const generateBarcode = async (
  type: string,
  text: string | number | boolean,
  width: number,
  height: number,
  format: string,
  dpi: number,
  showText: boolean,
  setIsLoading: (isLoading: boolean) => void,
  setError: (error: string | null) => void,
  setIsLimitExceeded: (isExceeded: boolean) => void
): Promise<string | null> => {
  setIsLoading(true);
  setError(null);

  const url = `${apiDomain}/api/generate?data=${encodeURIComponent(text.toString())}&format=${type}&width=${width}&height=${height}&image_format=${format}&dpi=${dpi}&center_text=${showText}`;

  try {
    const response = await fetch(url);

    if (!response.ok) {
      if (response.status === 429) {
        setIsLimitExceeded(true);
        throw new Error('Usage limit exceeded. Please try again tomorrow.');
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const blob = await response.blob();
    const imageUrl = URL.createObjectURL(blob);
    setIsLoading(false);
    return imageUrl;

  } catch (e) {
    setIsLoading(false);
    if (e instanceof Error) {
      setError(e.message);
    } else {
      setError('An unknown error occurred');
    }
    return null;
  }
};

export const cleanupBarcodeUrl = (url: string) => {
  URL.revokeObjectURL(url);
};
