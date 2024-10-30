import { Button } from "@/components/ui/button"
import { Printer } from "lucide-react"

interface PrintButtonProps {
    barcodeUrl: string;
}

export function PrintButton({ barcodeUrl }: PrintButtonProps) {
    const handlePrint = () => {
        const printWindow = window.open('', '_blank');
        if (printWindow) {
            printWindow.document.write(`
                <html>
                <head>
                    <title>theBarcodeAPI Barcode</title>
                    <style>
                        body {
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                        }
                        img {
                            max-width: 100%;
                            max-height: 100%;
                        }
                    </style>
                </head>
                <body>
                    <img src="${barcodeUrl}" alt="Generated Barcode" onload="window.onImageLoad()" />
                </body>
                <script>
                    window.onImageLoad = function() {
                        setTimeout(() => {
                            window.print();
                            setTimeout(() => {
                                window.close();
                            }, 500);
                        }, 100);
                    }
                </script>
                </html>
            `);
            printWindow.document.close();
            printWindow.focus();
        }
    }

    return (
        <Button variant="outline" className="flex-1 bg-black text-white" onClick={handlePrint}>
            <Printer className="w-4 h-4 mr-2" />
            Print
        </Button>
    )
}