/**
 * WARSCAN - PDF Export Controller
 */

const PdfExport = {
    async generate() {
        if (typeof jspdf === 'undefined' || typeof html2canvas === 'undefined') {
            alert('PDF export libraries not loaded.');
            return;
        }

        const { jsPDF } = jspdf;
        const doc = new jsPDF('p', 'mm', 'a4');
        const pageWidth = 210;
        const margin = 15;
        let y = margin;

        // Header
        doc.setFillColor(10, 10, 15);
        doc.rect(0, 0, pageWidth, 40, 'F');
        
        doc.setTextColor(255, 255, 255);
        doc.setFontSize(24);
        doc.setFont('helvetica', 'bold');
        doc.text('WARSCAN', margin, 25);
        
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        doc.text('Evacuation Plan', margin, 32);

        y = 50;

        // Date
        doc.setTextColor(100, 100, 100);
        doc.setFontSize(9);
        doc.text(`Generated: ${new Date().toLocaleString()}`, margin, y);
        y += 10;

        // Route info
        doc.setTextColor(0, 0, 0);
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('Route Summary', margin, y);
        y += 8;

        const distance = document.getElementById('route-distance')?.textContent || '--';
        const duration = document.getElementById('route-duration')?.textContent || '--';

        doc.setFontSize(11);
        doc.setFont('helvetica', 'normal');
        doc.text(`Distance: ${distance} km`, margin, y);
        y += 6;
        doc.text(`Estimated Time: ${duration} minutes`, margin, y);
        y += 12;

        // Map screenshot
        const mapEl = document.getElementById('map');
        if (mapEl) {
            try {
                const canvas = await html2canvas(mapEl, {
                    useCORS: true,
                    allowTaint: true,
                    scale: 1
                });
                const imgData = canvas.toDataURL('image/jpeg', 0.8);
                const imgWidth = pageWidth - (margin * 2);
                const imgHeight = (canvas.height / canvas.width) * imgWidth;
                
                doc.addImage(imgData, 'JPEG', margin, y, imgWidth, Math.min(imgHeight, 100));
                y += Math.min(imgHeight, 100) + 10;
            } catch (e) {
                console.warn('Map screenshot failed:', e);
            }
        }

        // Directions
        if (y > 200) {
            doc.addPage();
            y = margin;
        }

        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('Directions', margin, y);
        y += 8;

        const steps = document.querySelectorAll('.route-step');
        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');

        steps.forEach((step, i) => {
            if (y > 270) {
                doc.addPage();
                y = margin;
            }

            const text = step.querySelector('.step-text')?.textContent || '';
            const dist = step.querySelector('.step-distance')?.textContent || '';
            
            doc.setFont('helvetica', 'bold');
            doc.text(`${i + 1}.`, margin, y);
            doc.setFont('helvetica', 'normal');
            
            const lines = doc.splitTextToSize(`${text} ${dist}`, pageWidth - margin * 2 - 10);
            doc.text(lines, margin + 8, y);
            y += lines.length * 5 + 3;
        });

        // Emergency contacts
        if (y > 220) {
            doc.addPage();
            y = margin;
        }

        y += 5;
        doc.setFontSize(14);
        doc.setFont('helvetica', 'bold');
        doc.text('Emergency Contacts', margin, y);
        y += 8;

        doc.setFontSize(10);
        doc.setFont('helvetica', 'normal');
        const contacts = [
            'Israel: Police 100 | Ambulance 101 | Fire 102',
            'Iran: Police 110 | Ambulance 115 | Fire 125',
            'USA: 911 (all emergencies)',
            'International Red Cross: +41 22 730 2111'
        ];

        contacts.forEach(contact => {
            doc.text(contact, margin, y);
            y += 5;
        });

        // Footer
        y = 285;
        doc.setFontSize(8);
        doc.setTextColor(150, 150, 150);
        doc.text('This document is for informational purposes only. Always follow official guidance.', margin, y);

        // Save
        doc.save(`warscan-evacuation-${Date.now()}.pdf`);
    }
};
