"""Starter examples for each Category, so predictions work before the user has
corrected anything. They're written the way merchants appear on US Statements.
The user's own corrections soon outweigh them (examples.SEED_WEIGHT).

"Other" has no examples: it's what's left when nothing is similar enough.
"""

SEEDS: dict[str, list[str]] = {
    "Dining": [
        "Starbucks", "McDonald's", "Chipotle Mexican Grill", "Chick-fil-A", "Subway",
        "Taco Bell", "Domino's Pizza", "Panera Bread", "Dunkin", "DoorDash", "Uber Eats",
        "Grubhub", "Restaurant", "Cafe", "Coffee shop", "Bar and grill", "Pizzeria", "Sushi",
        "Burger", "Bakery", "Brewery", "Diner",
    ],
    "Education": [
        "Tuition payment", "University bursar", "College bookstore", "Coursera", "Udemy",
        "Chegg", "Khan Academy", "School supplies", "Pearson education", "Student loan",
    ],
    "Entertainment": [
        "AMC Theatres", "Regal Cinemas", "Ticketmaster", "StubHub", "Steam games",
        "PlayStation Network", "Xbox", "Nintendo eShop", "Bowling alley", "Concert tickets",
        "Movie theater", "Museum admission", "Theme park", "Golf course",
    ],
    "Fees & Interest": [
        "Interest charge on purchases", "Interest charged", "Late fee", "Annual membership fee",
        "Foreign transaction fee", "Overdraft fee", "Monthly service fee", "Cash advance fee",
        "Returned payment fee", "ATM fee", "Wire transfer fee",
    ],
    "Groceries": [
        "Whole Foods Market", "Trader Joe's", "Kroger", "Safeway", "Publix", "Aldi",
        "H-E-B", "Wegmans", "Costco wholesale", "Sam's Club", "Instacart", "Albertsons",
        "Food Lion", "Giant Eagle", "Sprouts Farmers Market", "Supermarket", "Grocery store",
        "WHOLEFDS", "TRADER JOE S", "KROGER FUEL", "HEB",
    ],
    "Health": [
        "Planet Fitness", "LA Fitness", "Equinox", "Peloton", "Doctor office", "Dentist",
        "Medical center", "Hospital", "Urgent care", "Labcorp", "Quest Diagnostics",
        "Optometrist", "Physical therapy", "Kaiser Permanente", "Gym membership",
    ],
    "Home": [
        "Home Depot", "Lowe's", "IKEA", "Bed Bath & Beyond", "Wayfair", "Ace Hardware",
        "Menards", "Furniture store", "Hardware store", "HomeGoods", "Crate & Barrel",
        "Lawn and garden", "Cleaning service", "Plumber",
    ],
    "Housing": [
        "Rent payment", "Apartment rent", "Property management", "Mortgage payment",
        "HOA dues", "Homeowners association", "Landlord", "Apartments leasing office",
    ],
    "Insurance": [
        "GEICO", "State Farm", "Progressive insurance", "Allstate", "Liberty Mutual",
        "Lemonade insurance", "Auto insurance", "Renters insurance", "Life insurance premium",
        "Health insurance premium",
    ],
    "Kids & Pets": [
        "Petco", "PetSmart", "Chewy", "Veterinary clinic", "Animal hospital", "Daycare",
        "Child care", "Babysitter", "Toys R Us", "Carter's kids clothing", "Pet supplies",
    ],
    "Personal Care": [
        "Hair salon", "Barber shop", "Nail salon", "Spa", "Massage", "Ulta Beauty",
        "Sephora", "Great Clips", "Supercuts", "Cosmetics", "Laundromat", "Dry cleaners",
    ],
    "Pharmacy": [
        "CVS Pharmacy", "Walgreens", "Rite Aid", "Duane Reade", "Pharmacy prescription",
        "Drugstore",
    ],
    "Shopping": [
        "Amazon", "Amazon Marketplace", "AMZN Mktp US", "AMAZON.COM AMZN.COM/BILL", "Target", "Walmart", "Best Buy", "Apple Store",
        "eBay", "Etsy", "Nordstrom", "Macy's", "TJ Maxx", "Marshalls", "Old Navy", "Gap",
        "Nike", "Kohl's", "Dollar Tree", "Department store", "Clothing store", "Electronics",
    ],
    "Subscriptions": [
        "Netflix", "Spotify", "Hulu", "Disney Plus", "HBO Max", "YouTube Premium",
        "Apple iCloud", "Apple Music", "Google One storage", "Amazon Prime membership",
        "Microsoft 365", "Adobe Creative Cloud", "Dropbox", "ChatGPT subscription",
        "Audible", "New York Times subscription", "Patreon", "APPLE.COM/BILL",
        "GOOGLE *YouTube",
    ],
    "Transport": [
        "Shell", "Chevron", "Exxon Mobil", "BP gas station", "Speedway", "Wawa", "Sunoco",
        "Costco gas", "Uber trip", "Lyft ride", "Parking garage", "Toll road", "E-ZPass",
        "Metro transit", "Car wash", "Jiffy Lube", "Auto repair", "Gas station",
    ],
    "Travel": [
        "Delta Air Lines", "United Airlines", "American Airlines", "Southwest Airlines",
        "JetBlue", "Marriott", "Hilton hotels", "Hyatt", "Airbnb", "Expedia", "Booking.com",
        "Hertz car rental", "Enterprise rent-a-car", "Amtrak", "Hotel", "Airline tickets",
    ],
    "Utilities": [
        "Electric company", "Power and light", "Gas utility", "Water utility", "Comcast Xfinity",
        "Spectrum internet", "AT&T", "Verizon wireless", "T-Mobile", "Internet service",
        "Phone bill", "VZWRLSS", "VERIZON WRLS", "TMOBILE AUTO PAY", "ATT BILL PAYMENT",
        "Waste management", "Sewer service", "Duke Energy", "PG&E",
    ],
}
