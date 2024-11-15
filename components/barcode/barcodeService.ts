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
  setIsLimitExceeded: (isExceeded: boolean) => void,
  customText?: string,
  centerText?: boolean
): Promise<string | null> => {
  setIsLoading(true);
  setError(null);

  const queryParams = new URLSearchParams({
    data: text.toString(),
    format: type.toLowerCase(),
    width: width.toString(),
    height: height.toString(),
    image_format: format.toUpperCase(),
    dpi: dpi.toString(),
    show_text: showText.toString(),
    center_text: (centerText ?? true).toString()
  });

  if (showText && customText) {
    queryParams.append('text_content', customText);
  }

  const url = `${apiDomain}/api/generate?${queryParams}`;

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
