import hashlib
import json
import time
import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from blockchain import Block, Blockchain

def calculate_hash(content):
    if isinstance(content, str):
        return hashlib.sha256(content.encode()).hexdigest()
    return hashlib.sha256(content).hexdigest()

def create_certificate_pdf(filename, name, degree, year, is_fake=False):
    # Setup canvas
    c = canvas.Canvas(filename, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # Draw border
    c.setStrokeColor(HexColor('#1E3A8A')) # Dark blue
    c.setLineWidth(10)
    c.rect(0.5*inch, 0.5*inch, width-1*inch, height-1*inch)
    
    # Draw inner border
    c.setStrokeColor(HexColor('#93C5FD')) # Light blue
    c.setLineWidth(2)
    c.rect(0.6*inch, 0.6*inch, width-1.2*inch, height-1.2*inch)
    
    # Try to draw the BPIT Logo if it exists
    # Using an absolute path to guarantee it's found
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
    if os.path.exists(logo_path):
        try:
            # Draw logo in top left corner (adjusted to fit better)
            c.drawImage(logo_path, 0.8*inch, height - 1.8*inch, width=1.5*inch, height=1*inch, preserveAspectRatio=True, mask='auto')
        except Exception as e:
            print(f"Warning: Could not render logo: {e}")

    # Title
    c.setFont("Helvetica-Bold", 36)
    c.setFillColor(HexColor('#1E3A8A'))
    if is_fake:
        # Subtle typo in the fake one: "Bhgwan" instead of "Bhagwan"
        c.drawCentredString(width/2, height - 1.8*inch, "Bhgwan Parshuram Institute of Technology")
    else:
        c.drawCentredString(width/2, height - 1.8*inch, "Bhagwan Parshuram Institute of Technology")
        
    # Subtitle
    c.setFont("Helvetica", 18)
    c.setFillColor(HexColor('#4B5563'))
    c.drawCentredString(width/2, height - 2.5*inch, "- OFFICIAL ACADEMIC TRANSCRIPT -")
    
    # Content
    c.setFont("Helvetica", 24)
    c.setFillColor(HexColor('#000000'))
    c.drawCentredString(width/2, height - 3.8*inch, "This certifies that")
    
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(width/2, height - 4.6*inch, name)
    
    c.setFont("Helvetica", 24)
    c.drawCentredString(width/2, height - 5.4*inch, "has successfully completed the degree of")
    
    c.setFont("Helvetica-Bold", 24)  # Slightly smaller to fit "Electronics and Communications"
    c.setFillColor(HexColor('#1E3A8A'))
    c.drawCentredString(width/2, height - 6.2*inch, degree)
    
    # Bottom details
    c.setFont("Helvetica", 14)
    c.setFillColor(HexColor('#000000'))
    c.drawString(1.5*inch, 1.5*inch, f"Date of Issue: {year}")
    
    cert_id = hashlib.md5(name.encode()).hexdigest()[:8].upper()
    c.drawString(1.5*inch, 1.2*inch, f"Certificate ID: BPIT-2026-{cert_id}")
    
    # Signatures
    c.line(width - 4.5*inch, 1.7*inch, width - 1.5*inch, 1.7*inch)  # Made signature line wider
    c.drawString(width - 4.5*inch, 1.5*inch, "Prof. Achal Kaushik")
    c.drawString(width - 4.5*inch, 1.2*inch, "Dean of Academics")
    
    c.save()

def generate_demo_files():
    print("Generating demo files...")
    
    degree_name = "Bachelor of Technology in Electronics and Communications"
    
    # Generate for team members
    create_certificate_pdf("raunak_gupta_diploma.pdf", "Raunak Gupta", degree_name, "2026", is_fake=False)
    create_certificate_pdf("harsh_jadaun_diploma.pdf", "Harsh Jadaun", degree_name, "2026", is_fake=False)
    create_certificate_pdf("mihir_kumar_diploma.pdf", "Mihir Kumar", degree_name, "2026", is_fake=False)
    create_certificate_pdf("satya_sunny_diploma.pdf", "Satya Sunny", degree_name, "2026", is_fake=False)
    
    # Create fake version for Satya Sunny for tamper demonstration
    create_certificate_pdf("satya_sunny_fake_diploma.pdf", "Satya Sunny", degree_name, "2026", is_fake=True)
    
    print("Created team certificates at BPIT.")
    
    with open("raunak_gupta_diploma.pdf", "rb") as f:
        raunak_content = f.read()

    with open("harsh_jadaun_diploma.pdf", "rb") as f:
        harsh_content = f.read()
        
    with open("mihir_kumar_diploma.pdf", "rb") as f:
        mihir_content = f.read()

    with open("satya_sunny_diploma.pdf", "rb") as f:
        satya_content = f.read()

    # Initialize Blockchain
    if os.path.exists("blockchain.json"):
        os.remove("blockchain.json")
    
    bc = Blockchain() # Creates genesis block automatically
    
    # Process the real photos to make them immutable
    print("Processing immutable holder photos...")
    os.makedirs(os.path.join("static", "uploads"), exist_ok=True)
    
    def process_photo(filename):
        if not os.path.exists(filename):
            print(f"Warning: Photo {filename} missing. Falling back to SVG.")
            return "placeholder_avatar.svg"
            
        with open(filename, "rb") as f:
            photo_data = f.read()
            
        photo_hash = hashlib.sha256(photo_data).hexdigest()
        ext = os.path.splitext(filename)[1]
        if ext == '.jpeg': ext = '.jpg'
        
        saved_filename = f"{photo_hash}{ext}"
        saved_path = os.path.join("static", "uploads", saved_filename)
        
        with open(saved_path, "wb") as f:
            f.write(photo_data)
        
        return saved_filename

    raunak_photo = process_photo("raunak_photo.jpeg")
    harsh_photo = process_photo("harsh_photo.jpeg")
    mihir_photo = process_photo("mihir_photo.jpeg")
    satya_photo = process_photo("satya_photo.jpeg")
    
    # Preload Demo Data
    # Calculate deterministic Cert IDs for the pre-load to match the PDF exactly
    raunak_cert = hashlib.md5("Raunak Gupta".encode()).hexdigest()[:8].upper()
    harsh_cert = hashlib.md5("Harsh Jadaun".encode()).hexdigest()[:8].upper()
    mihir_cert = hashlib.md5("Mihir Kumar".encode()).hexdigest()[:8].upper()
    satya_cert = hashlib.md5("Satya Sunny".encode()).hexdigest()[:8].upper()

    import random
    from datetime import datetime, timedelta
    
    # Generate random timestamp between 1 and 30 days ago
    def random_past_timestamp():
        days_ago = random.randint(1, 30)
        past_date = datetime.now() - timedelta(days=days_ago)
        return past_date.timestamp()

    # Add the blocks. We manually override the timestamp to simulate historical data
    b1 = bc.add_block("Academic Certificate", "Bhagwan Parshuram Institute of Technology", calculate_hash(raunak_content), 
                 student_name="Raunak Gupta", cert_id=f"BPIT-2026-{raunak_cert}", validity="Lifetime", student_image=raunak_photo)
    b1.timestamp = random_past_timestamp()
    b1.block_hash = b1.calculate_block_hash()
                 
    b2 = bc.add_block("Academic Certificate", "Bhagwan Parshuram Institute of Technology", calculate_hash(harsh_content), 
                 student_name="Harsh Jadaun", cert_id=f"BPIT-2026-{harsh_cert}", validity="Lifetime", student_image=harsh_photo)
    b2.timestamp = random_past_timestamp()
    b2.block_hash = b2.calculate_block_hash()
                 
    b3 = bc.add_block("Academic Certificate", "Bhagwan Parshuram Institute of Technology", calculate_hash(mihir_content), 
                 student_name="Mihir Kumar", cert_id=f"BPIT-2026-{mihir_cert}", validity="Lifetime", student_image=mihir_photo)
    b3.timestamp = random_past_timestamp()
    b3.block_hash = b3.calculate_block_hash()

    b4 = bc.add_block("Academic Certificate", "Bhagwan Parshuram Institute of Technology", calculate_hash(satya_content), 
                 student_name="Satya Sunny", cert_id=f"BPIT-2026-{satya_cert}", validity="Lifetime", student_image=satya_photo)
    b4.timestamp = random_past_timestamp()
    b4.block_hash = b4.calculate_block_hash()
    
    # Save the modified timestamps to the json file
    bc.save_chain()

    print("Pre-loaded 4 dummy blocks into blockchain.json")
    print("\n--- DEMO SETUP COMPLETE ---")
    print("You can now run: python app.py")
    print("In your demo, use 'satya_sunny_diploma.pdf' to show VERIFIED.")
    print("Use 'satya_sunny_fake_diploma.pdf' to show TAMPERED.")

if __name__ == "__main__":
    generate_demo_files()
