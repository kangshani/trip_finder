#!/usr/bin/env python3
"""
One-time script to fix attraction names flagged by audit_attractions.py.
Maps old names to corrected noun-form names.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent  # scripts/ -> enrich-attractions/ -> skills/ -> .claude/ -> project root
DATA_DIR = PROJECT_ROOT / "data" / "destinations"

# ── Fix map: file -> {old_name: new_name} ────────────────────────────────────
# None means "remove this attraction entirely" (blog artifacts, not real attractions)

FIXES = {
    "amsterdam-netherlands-summer.json": {
        "Get Oriented with a Walking Tour": "Amsterdam Canal Walking Tour",
        "Learn About Dutch History at the Rijksmuseum": "Rijksmuseum",
        "Get Inside an Artist's Mind at the Van Gogh Museum": "Van Gogh Museum",
        "Visit The Anne Frank House": "Anne Frank House",
        "Dive Deeper into the History of Amsterdam's Jewish Community": "Jewish Cultural Quarter",
        "Eat Some Pickled Herring": "Dutch Herring Tasting",
        "Hit the Albert Cuyp Market in De Pijp": "Albert Cuyp Market",
        "…And Explore the Rest of De Pijp": "De Pijp Neighborhood",
        "Let's Talk About Amsterdam's Red Light District": "Red Light District",
        "Explore the Jordaan": "The Jordaan",
    },
    "athens-greece-summer.json": {
        "All the best things to do in Athens for first-time visitors": None,
        "The Acropolis: legends carved in marble": "The Acropolis",
        "Acropolis Museum: the Parthenon's stories unveiled": "Acropolis Museum",
        "Temple of Zeus: the God of Gods": "Temple of Olympian Zeus",
        "Ancient Agora: the pulse of ancient Athens": "Ancient Agora",
        "Roman Agora and Tower of the Winds: predicting ships arriving": "Roman Agora and Tower of the Winds",
        "Panathenaic Stadium: marble glory and Olympic dreams": "Panathenaic Stadium",
        "Syntagma (Constitution) Square: the centre of Athens": "Syntagma Square",
        "Changing of the Guards: precision in motion": "Changing of the Guard",
        "National Garden: a serene escape in the heart of Athens": "National Garden",
    },
    "azores-portugal-summer.json": {
        "Itineraries": None,
        "São Miguel and other islands": None,
        "Visit Europe's oldest tea plantation": "Gorreana Tea Plantation",
        "Hike amongst UNESCO World Heritage vineyards": "Pico Island Vineyards",
        "Feast on geothermal-cooked Cozido": "Cozido das Furnas",
        "Go whale-watching in the Azores": "Whale Watching",
        "Swim in geothermal lakes": "Furnas Hot Springs",
        "Go back in time in Angra do Heroismo": "Angra do Heroismo",
        "Trek across the black sands of Capelinhos volcano": "Capelinhos Volcano",
        "Ascend Pico Alto": "Pico Alto",
    },
    "bangkok-thailand-summer.json": {
        "Map of Bangkok": None,
        "best things to do and see in Bangkok": None,
        "Grand Palace – Bangkok's most iconic tourist attraction": "Grand Palace",
        "Wat Pho – The Reclining Buddha": "Wat Pho",
        "Wat Arun – The striking Temple of Dawn": "Wat Arun",
        "Khao San Road – Lively backpacker street": "Khao San Road",
        "Enjoy the sunset from a rooftop bar – See Bangkok's glittering lights from above": "Rooftop Bars",
        "Chatuchak Weekend Market – Thailand's largest market": "Chatuchak Weekend Market",
        "Bangkok's shopping malls – Shopping for all budgets in cool air conditioning": "Bangkok Shopping Malls",
        "Wat Saket and Golden Mount – Temple with views over Bangkok": "Wat Saket and Golden Mount",
    },
    "bologna-italy-summer.json": {
        "Get your ticket": None,
        "The Quadrilatero area": "Quadrilatero Market District",
        "The city's museums": None,
        "The little window of via Piella": "Finestrella di Via Piella",
    },
    "borneo-malaysia-summer.json": {
        "Top Things to Do in Borneo": None,
        "Climb Mount Kinabalu": "Mount Kinabalu",
        "Explore Gunung Mulu National Park": "Gunung Mulu National Park",
        "Relax on Tropical Islands": "Sipadan Island",
    },
    "buenos-aires-argentina.json": {
        "Best Things To Do In Buenos Aires": None,
        "Savor the Best Meat of Your Life at an Asado": "Traditional Asado",
        "Experience the Culture of Mate at a Tasting": "Mate Tasting Experience",
        "Experience the Passion of a Tango Show": "Tango Show",
        "Explore Recoleta Cemetery": "Recoleta Cemetery",
        "Indulge in Argentine Wine at a Tasting": "Argentine Wine Tasting",
        "Dine at Don Julio, the 10th Best Restaurant in the World": "Don Julio Restaurant",
        "Cheer for Boca Juniors or River Plate at a Fútbol (Soccer) Match": "La Bombonera Stadium",
        "Marvel at the Beauty of Teatro Colón": "Teatro Colón",
        "Escape to the Tranquility of the Tigre Delta": "Tigre Delta",
    },
    "cairo-luxor-egypt.json": {
        "Map of Unique Things to Do in Luxor Egypt": None,
        "Unique Things to Do in Luxor Other Than Temples": None,
        "Explore the Valley of the Kings Tombs": "Valley of the Kings",
        "See the Colossi of Memnon at Sunrise": "Colossi of Memnon",
        "Visit Luxor's Best Museums": "Luxor Museum",
        "Sail the Nile on a Sunset Felucca Ride": "Nile Felucca Cruise",
        "Shop for Souvenirs at Luxor Bazaars": "Luxor Bazaars",
        "Try Traditional Egyptian Food in Luxor": "Traditional Egyptian Cuisine",
        "Best Temples to Visit in Luxor Egypt": None,
        "Explore Karnak Temple": "Karnak Temple",
    },
    "copenhagen-denmark-summer.json": {
        "All My Copenhagen Guides. Delivered.": None,
        "Rent a Bike and Explore Copenhagen": "Copenhagen by Bike",
        "Enjoy One of Copenhagen's Many Great Views": None,
        "Go to Kastellet": "Kastellet",
        "Visit Amager Strand": "Amager Strand",
        "Go for a Boat Tour Around Copenhagen": "Copenhagen Canal Tour",
        "Wander Along Nyhavn": "Nyhavn",
        "Discover the Charm of Christianshavn": "Christianshavn",
    },
    "corsica-france-summer.json": {
        "Hike the GR20 (aka Fra li Monti)": "GR20 Trail",
        "Explore the ancient churches of CargÃ¨se": "Churches of Cargèse",
        "â3. Drive from Francardo to Porto": "Francardo to Porto Scenic Drive",
        "ââ4. Get to know NapolÃ©on in Ajaccio": "Maison Bonaparte, Ajaccio",
        "â5. Traverse the island by train": "Corsican Railway",
        "Find Bastiaâs historic heart": "Bastia Old Town",
        "Discover seven centuries of island history": "Corte Citadel",
        "Take the stairs to the black sand beach in Nonza": "Nonza Black Sand Beach",
        "Marvel at the clifftop beauty of Bonifacio from the sea": "Bonifacio Cliffs",
        "Follow in the footsteps of customs officers": "Sentier des Douaniers",
    },
    "costa-rica-summer.json": {
        "Try a Copo or a Churchill": "Copo and Churchill Treats",
        "Enjoy the Fiestas Civicas(Local Parties)": "Fiestas Cívicas",
        "Cruise Through the Gulf of Nicoya to Tortuga Island": "Tortuga Island",
        "Go On a Bioluminesence Kayak Tour in Paquera": "Bioluminescence Kayak Tour",
    },
    "dubrovnik-to-split-coast-croatia-summer.json": {
        "Explore Old Town of Dubrovnik": "Dubrovnik Old Town",
        "People watch from the pavements of Riva in Split": "Riva Promenade, Split",
        "Spend a Sunday at Marjan Hill": "Marjan Hill",
        "Visit the Cathedral of St. James in Šibenik": "Cathedral of St. James, Šibenik",
        "Lend an ear to the Sea Organ in Zadar": "Sea Organ, Zadar",
        "Bike along the Mljet Island National Park": "Mljet Island National Park",
        "Perch up at the counter of a Konoba in Split": "Traditional Konoba Dining",
        "Fill up in style at Sibenik's Michelin-starred restaurant": "Pelegrini Restaurant, Šibenik",
        "Discover the Adriatic Sea by kayaking to Makarska Riviera": "Makarska Riviera",
    },
    "edinburgh-scotland-summer.json": {
        "Top Edinburgh Hotels": None,
        "Sights in Edinburgh you can't miss": None,
        "Go to the fairytale Dean Village": "Dean Village",
        "Stroll down Circus Lane": "Circus Lane",
        "Pretend you're at a ball at the New College": "New College",
        "Explore the majestic Edinburgh Castle": "Edinburgh Castle",
        "Wander along The Royal Mile": "The Royal Mile",
        "Hike to the top of Arthur's Seat": "Arthur's Seat",
        "Spot the best views of Edinburgh Castle at the Vennel Viewpoint": "The Vennel Viewpoint",
        "Visit the Harry Potter shops on Victoria Street": "Victoria Street",
    },
    "ha-long-bay-vietnam-summer.json": {
        "Snorkel and Dive to Explore Coral Reefs": "Coral Reef Snorkeling and Diving",
        "Explore Ha Long by Cruise Boat": "Ha Long Bay Cruise",
        "Hike to Hidden Caves on Cat Ba Island": "Cat Ba Island Caves",
        "Check out Hon Ga Choi (Fighting Cock Islet)": "Hon Ga Choi Islet",
        "oops": None,
    },
    "hanoi-vietnam-summer.json": {
        "Start with a guided scooter tour": "Hanoi Scooter Tour",
        "Wander the famous Hanoi train street": "Hanoi Train Street",
        "Have drinks at the Diamond Sky Bar": "Diamond Sky Bar",
        "Eat the same Bun Cha as Obama and Bourdain": "Bun Cha Huong Lien",
        "Stroll around the Old Quarter": "Hanoi Old Quarter",
        "Drink ALL the Vietnamese coffee": "Vietnamese Coffee Culture",
        "Explore the Tran Quoc Pagoda": "Tran Quoc Pagoda",
        "Visit the Temple of Literature": "Temple of Literature",
        "Drink cheap beer at beer street after dark": "Ta Hien Beer Street",
        "Check out the Imperial Citadel": "Imperial Citadel of Thang Long",
    },
    "hawaii.json": {
        "The Ultimate Hawaii Bucket List: Things to Do in Hawaii": None,
        "Best Things to Do on Big Island": None,
        "Best Things to Do on Kauai": None,
        "Best Things to Do on Maui": None,
        "Best Things to Do on Molokai": None,
        "Best Things to Do on Oahu": None,
        "Best Things to Do on Lanai": None,
        "Reader Interactions": None,
    },
    "jordan-summer.json": {
        "Discover the ancient place of Petra": "Petra",
        "Adventure in the Wadi Rum desert": "Wadi Rum",
        "Visit the biblical sights of Jordan": "Biblical Sites of Jordan",
        "Swimming in Dead sea": "Dead Sea",
        "Warm yourself in the hot waterfalls of Ma'in": "Ma'in Hot Springs",
        "Walking in Wadi Mujib gorge": "Wadi Mujib",
        "Eat Jordan meals": "Jordanian Cuisine",
        "Rest and diving on the Red Sea in Aqaba": "Aqaba Red Sea",
        "Go to the ruins of Jerash": "Jerash Ruins",
        "Travel Jordan by car": None,
    },
    "kyrgyzstan-summer.json": {
        "Uncover a treasure trove of cultural and natural gems": None,
        "1Visit the idyllic Issyk-Kul Lake": "Issyk-Kul Lake",
        "2Admire the sublime scenery of Skazka Canyon": "Skazka Canyon",
        "3Explore the remains of ancient Balasagun at the Burana Tower": "Burana Tower",
        "4Soak up the atmosphere in Ala-Too Square": "Ala-Too Square",
        "5Shop for souvenirs at Osh Bazaar": "Osh Bazaar",
        "6Go hiking in Ala-Archa National Park": "Ala-Archa National Park",
        "7Discover exquisite local handicrafts": "Kyrgyz Handicrafts",
        "8Marvel Chon-Kemin's valleys and forests": "Chon-Kemin Valley",
        "9Immerse yourself in Kyrgyz culture at a traditional festival": "Kyrgyz Cultural Festivals",
    },
    "lisbon-portugal-summer.json": {
        "Best Things to Do in Lisbon": None,
        "Make the Hike Up To Castelo de São Jorge": "Castelo de São Jorge",
        "Have Lunch at Miradouro de Santa Luzia": "Miradouro de Santa Luzia",
        "Hop the Elevador da Glória & Admire Some Street Art in Lisbon": "Elevador da Glória",
        "Get Debaucherous On Pink Street": "Pink Street (Rua Nova do Carvalho)",
        "Have Your Sins Forgiven at Mosteiro dos Jerónimos": "Mosteiro dos Jerónimos",
        "Jardim Botânico da Ajuda for One of the Most Relaxing Things to Do in Lisbon": "Jardim Botânico da Ajuda",
        "Inspire Yourself at Lx Factory & Village Underground": "LX Factory",
        "Devour Amazing Food at Time Out Market in Lisbon, Portugal": "Time Out Market",
        "Need More Things to Do? Catch a Sunset at Hotel Mundial's Rooftop Bar": "Hotel Mundial Rooftop Bar",
    },
    "lofoten-islands-norway-summer.json": {
        "Best Things to Do in the Lofoten Islands": None,
        "Enjoy the Gorgeous Views": None,
        "Go to the Beach": "Lofoten Beaches",
        "Go Surfing": "Arctic Surfing",
        "Conquer One (or More) of the Epic Hiking Trails": "Lofoten Hiking Trails",
        "Stay in a Rorbu": "Traditional Rorbu Cabins",
        "Explore the Towns and Fishing Villages": "Reine and Fishing Villages",
        "Visit Historic Nusfjord": "Nusfjord",
        "Eat the Local Cuisine": "Lofoten Seafood",
        "Climb Svolvaergeita": "Svolværgeita",
    },
    "luang-prabang-laos-summer.json": {
        "Map Of Luang Prabang's Best Things To Do": None,
        "Trek To Phousi Hill": "Phousi Hill",
        "Visit The Buddhist Temples": "Buddhist Temples of Luang Prabang",
        "Explore The Night Market": "Luang Prabang Night Market",
        "Take River Cruise": "Mekong River Cruise",
        "Visit Kuang Si Falls": "Kuang Si Falls",
        "Visit The Royal Palace Museum & Haw Phra Bang": "Royal Palace Museum",
        "Relaxing Coffee At Dyen Sabai": "Dyen Sabai",
        "Ferry across Nam Khan River": "Nam Khan River",
    },
    "maldives-summer.json": {
        "Get certified in scuba": "Scuba Diving Certification",
        "Dine, drink or detox underwater": "Underwater Dining",
        "Admire the marine life â without a scuba tank": "Snorkeling and Marine Life",
        "Learn about the Maldivesâ rich history": "Maldives National Museum",
        "Visit a âlocalâ Maldivian island": "Local Island Visit",
        "Go skydiving": "Skydiving over the Atolls",
        "Adopt your very own piece of coral": "Coral Reef Conservation",
        "Take yourMaldivestrip with Lonely Planet Journeys": None,
    },
    "marrakech-morocco-summer.json": {
        "Marrakech 101": None,
        "The Best Things to do in Marrakech": None,
        "Shop the Souks": "Marrakech Souks",
        "Read More: My Marrakech Travel Hub": None,
        "Shop Marrakech Outfits": None,
        "Stay in a Riad": "Traditional Riad Stay",
        "Discover Local Cuisine": "Moroccan Cuisine",
    },
    "masai-mara-kenya-summer.json": {
        "Witness the Wildebeest Migration": "Great Wildebeest Migration",
        "Set out on your Safari Game Drive": "Safari Game Drive",
        "Hover Above the Mara in a Hot Air Balloon": "Hot Air Balloon Safari",
        "Create Memories with the Maasai on Cultural Visits": "Maasai Cultural Visit",
        "Witness Iconic Wildlife on Walking Safaris": "Walking Safari",
        "Marvel at the Mara River": "Mara River",
        "Be Amazed by Mara Birdlife": "Mara Birdlife",
        "Moonlit Moments in the Masai Mara": "Night Safari",
        "Try Your Hand At The Bushtops Bushcraft Challenge": "Bushtops Bushcraft Challenge",
        "Admire Mornings on the Mara with Al fresco Dining": "Bush Breakfast",
    },
    "montenegro-summer.json": {
        "Delve into history at the National Museum of Montenegro in Cetinje": "National Museum of Montenegro, Cetinje",
        "Explore the atmospheric chambers of Lipa Cave": "Lipa Cave",
        "Take in the scenery at LovcÃ©n National Park": "Lovćen National Park",
        "Stroll around Podgoricaâs Ottoman old town": "Podgorica Old Town",
        "Gaze at the cliff-edge Ostrog Monastery": "Ostrog Monastery",
        "Encounter ancient history in Budva": "Budva Old Town",
        "Discover fantastic fortresses in Herceg Novi": "Herceg Novi Fortresses",
        "Explore the wild reaches of Mt Orjen": "Mount Orjen",
    },
    "montreal-canada-summer.json": {
        "History of Montréal": None,
        "Must visit places to eat and drink in Montréal": None,
        "Best Things to Do in Montreal": None,
        "Visit the Underground City": "Underground City (RÉSO)",
        "Best Things to Do in Montréal": None,
    },
    "namibia-summer.json": {
        "| A hot-air balloon flight over the desert": "Hot Air Balloon over Sossusvlei",
        "| Visitthe video of the hot-air balloon flight hereand all our travel videos onour Youtube channel": None,
        "| Kayak or catamaran excursion on Pelican Point": "Pelican Point Kayaking",
        "| An unforgettable parachute jump or a flight in a small plane": "Scenic Flight over Skeleton Coast",
        "| Dune surfing": "Dune Surfing",
        "| Visitsurf video hereand all our travel videos onour Youtube channel": None,
        "| Explore the Sandwich Harbour dunes in a 4X4": "Sandwich Harbour",
        "| Watching felines on a game drive": "Etosha Game Drive",
        "| Hiking in the country's various parks": "Namibian National Parks",
        "|Visit Swakopmund in a different way with local guides": "Swakopmund",
    },
    "oaxaca-mexico-summer.json": {
        "The Best Things to Explore in Oaxaca City": None,
        "Visit theMercado 20 Noviembre": "Mercado 20 de Noviembre",
        "Visit the HistoricMonte AlbánRuins": "Monte Albán",
        "Explore Jalatlaco Neighborhood": "Jalatlaco Neighborhood",
        "Eat at Humar": "Humar Restaurant",
        "Visit the Textiles Museum": "Museo Textil de Oaxaca",
        "Visit the Tlacolua Mercade (indigenous market)": "Tlacolula Market",
        "Eat at BEST El Pastor in Oaxaca": "Tacos al Pastor",
    },
    "oman.json": {
        "Top things to do in Oman – Hike and Swim in Wadi Shab": "Wadi Shab",
        "Explore the Sultan Qaboos Grand Mosque": "Sultan Qaboos Grand Mosque",
        "Watch Sunrise in Wahiba Sands – best of Oman scenery": "Wahiba Sands",
        "Swim in Wadi Bani Khalid – Beautiful Oman Landscapes": "Wadi Bani Khalid",
        "Climb on top of the Nizwa Fort": "Nizwa Fort",
        "Get dizzy in Jebel Shams": "Jebel Shams",
        "Watch the Fishermen throw nets": "Mutrah Fish Market",
        "About fishing in Oman": None,
        "Snorkel or dive": "Daymaniyat Islands Snorkeling",
    },
    "palawan-philippines-summer.json": {
        "Go Island Hopping in El Nido!": "El Nido Island Hopping",
        "Chill Out in Port Barton!": "Port Barton",
        "Visit Palawan's Beautiful Beaches!": "Palawan Beaches",
        "Head to Coron on a Multiple-Day Expedition!": "Coron Island",
        "Visit the Puerto Princesa Underground River!": "Puerto Princesa Underground River",
        "Go Diving in Palawan and Explore Fascinating Underwater Worlds!": "Palawan Diving",
        "Go Surfing at Duli Beach!": "Duli Beach",
        "Head off the Beaten Path in Southern Palawan!": "Southern Palawan",
        "Explore Palawan's Waterfalls!": "Palawan Waterfalls",
        "Explore the Surrounding Islands by Kayak!": "Island Kayaking",
    },
    "pantanal-brazil-summer.json": {
        "About the Pantanal": None,
        "Book your trip for the Pantanal in Brazil with PlanetaEXO": None,
        "Read more!": None,
        "Previous Post10 Pantanal travel tips for an unforgettable trip": None,
    },
    "paris-france-summer.json": {
        "Haven't got time to finish this post now?": None,
        "Here's my list of the best must-dos in Paris:": None,
        "Visit Monet's ACTUAL Gardens": "Giverny (Monet's Gardens)",
    },
    "patagonia-argentina.json": {
        "Key Takeaways: What to Know Before Visiting Argentine Patagonia": None,
        "Key Destinations to Prioritize": None,
        "Getting There and Getting Around": None,
        "My experience in Argentine Patagonia": None,
        "Distances Are Longer Than They Look (Much Longer)": None,
        "The Weather Will Change Repeatedly": None,
        "Wind Is the Real Challenge in Patagonia": None,
        "Flexibility Is Great But Reservations Matter More": None,
        "You Don't Have to Be an Expert Hiker": None,
        "A Short Visit": None,
    },
    "plitvice-lakes-croatia-summer.json": {
        "Save up to $3,000* per couple on your first Premium Tour": None,
        "Visit the Visitor Center:": "Visitor Center",
        "Hiking and Walking Trails:": "Hiking and Walking Trails",
        "Boat Rides:": "Lake Boat Rides",
        "Photography:": None,
        "Wildlife Watching:": "Wildlife Watching",
        "Educational Tours:": "Educational Tours",
        "Plitvice Lakes National Park admission tickets and fees": None,
        "Keep exploring": None,
        "Milder Weather, Smaller Crowds, Lower Prices: Why Europe in Spring is the Best Time to Visit": None,
    },
    "prague-czech-republic-summer.json": {
        "Walk Along Charles Bridge": "Charles Bridge",
        "Wander Around Malá Strana": "Malá Strana",
        "Visit Old Town Square": "Old Town Square",
        "Climb A Tower For Amazing Views": "Old Town Hall Tower",
    },
    "raja-ampat-indonesia-summer.json": {
        "Bird Watching in Raja AmpatRed Bird of Paradise and Wilson's Bird of Paradise": "Raja Ampat Bird Watching",
        "Best Time to See Raja Ampat's Birds of Paradise": None,
        "Listen to the podcast!": None,
    },
    "rome-italy-summer.json": {
        # Rome is mostly clean, only one food-tour style name
        "Rome Food Tour in Trastevere Neighborhood": "Trastevere Food Tour",
    },
    "san-sebastian-spain-summer.json": {
        "Places You Can't Miss on Your Visit": None,
    },
    "santorini-greece-summer.json": {
        "My Top 10 best things to do in Santorini": None,
        "Admire the island from a catamaran": "Catamaran Cruise",
        "Enjoy the peace of Oia at sunrise": "Oia at Sunrise",
        "Or face the crowds to watch sunset from Oia": "Oia Sunset",
        "Enjoy the angles of Emporio": "Emporio Village",
        "Take hundreds of pictures at Vlychada Beach": "Vlychada Beach",
        "Be amazed by the cliffs of Red Beach": "Red Beach",
        "Walk down to Ammoudi Bay": "Ammoudi Bay",
        "Travel back in time at the Akrotiri Archeological site": "Akrotiri Archaeological Site",
    },
    "sardinia-italy-summer.json": {
        "Wonderful Things To Do In Sardinia": None,
        "Enjoy the beaches": "Sardinian Beaches",
        "Go sailing (or on a boat tour)": "Boat Tour of La Maddalena Archipelago",
        "Explore Cagliari": "Cagliari",
        "Check out other cities in Sardinia": None,
        "Pop by the small towns and villages": "Sardinian Villages",
        "Visit some unique archeological sites": "Nuraghe Su Nuraxi",
        "Go to a Fairy's House or a Giant's Tomb": "Tomba dei Giganti",
        "Check out the Sardinian mines": "Sardinian Mines (Porto Flavia)",
        "Or the caves": "Neptune's Grotto",
    },
    "scottish-highlands-summer.json": {
        "Visit the Highland Castles": "Highland Castles",
    },
    "serengeti-tanzania-summer.json": {
        "Entrance fees to visit Serengeti National Park?": None,
        "Need more information?": None,
        "Spend Time on Game Drives": "Serengeti Game Drives",
        "Stop at the Serengeti Visitor Center": "Serengeti Visitor Center",
        "Visit a Maasai Village": "Maasai Village Visit",
        "Experience a Night Game Drive": "Night Game Drive",
    },
    "sri-lanka-summer.json": {
        "ADVENTURE EXPERIENCES | THE BEST PLACES TO VISIT IN SRI LANKA": None,
        "JUMP ON SRI LANKA'S SOUTHERN COAST ROPE SWINGS": "Southern Coast Rope Swings",
        "welcome to paradise:sri lanka's popular unawatuna beach": "Unawatuna Beach",
        "HIKE TO THE TOP OF SRI LANKA, ADAM'S PEAK (SRI PADA)": "Adam's Peak (Sri Pada)",
        "LEARN TO SURF IN WELIGAMA": "Weligama Surfing",
        "ADMIRE THE STUNNING NINE ARCH BRIDGE, ELLA": "Nine Arch Bridge, Ella",
        "Everything you need to know before visitingthe Nine Arch Bridge, Ella": None,
        "HIKE TO THE TOP OF ELLA ROCK": "Ella Rock",
        "Hill Country Exploring | Our guide toElla, Sri Lanka": None,
    },
    "tbilisi-georgia-summer.json": {
        "quick Tbilisi tips for your trip": None,
        "Tbilisi is just the beginning…": None,
        "awesome things to do in Tbilisi: The ultimate list": None,
        "Overall best things to do in Tbilisi": None,
        "Sip coffee inside a former Soviet sewing factory": "Fabrika Tbilisi",
        "Go for a scrub at the Abanotubani Sulfur Baths": "Abanotubani Sulfur Baths",
        "Explore the storied Kala & enchanting Sololaki neighbourhoods by foot": "Kala and Sololaki Neighborhoods",
        "Say Salve to Tbilisi's painted entryways": "Tbilisi's Painted Entryways",
        "Embrace Italian courtyard culture": "Italian Courtyards of Tbilisi",
        "Comb through kitsch at the Dry Bridge Flea Market": "Dry Bridge Flea Market",
    },
    "tokyo-japan-summer.json": {
        "Explore By Interest": None,
        "Tokyo tourist attractions": None,
        "Get to know the history of Edo and more at Tokyo historical sites": "Edo-Tokyo Museum",
        "Take your date to these romantic places in Tokyo for an unforgettable experience": None,
        "Discover the unknown: unique places and hidden spots in Tokyo": None,
        "Best ways to get around: transportation for sightseeing": None,
        "Tourist buses in Tokyo": None,
        "Train passes especially for tourists": None,
        "Other modes of transportation": None,
        "Best places to stay near major attractions": None,
    },
    "washington-dc-summer.json": {
        "Haven't got time to finish this post now?": None,
        "Visit the new People's House": "The White House Visitor Center",
        "Visit the beautiful Monuments": "National Mall Monuments",
        "Visit the White House": "The White House",
    },
    "zhangjiajie-china-summer.json": {
        "No.1: Explore Avatar Hallelujah Mountain in Zhangjiajie National Forest Park": "Avatar Hallelujah Mountain",
        "No.2: Challenge Yourselves over Zhangjiajie Glass Bridge": "Zhangjiajie Glass Bridge",
        "No.3: Pay a Visit to Tianmen Mountain with Fantastic Thrilling Experience": "Tianmen Mountain",
        "No.4: Capture Best View of Ever-changing Mysterious Tianzi Mountain": "Tianzi Mountain",
        "No.5: Hike along the Tranquil Golden Whip Stream": "Golden Whip Stream",
        "No.6: Shoot Panoramic View of Zhangjiajie National Forest Park at Huangshizhai": "Huangshizhai Viewpoint",
        "No.7: Take the Sightseeing Tram to Travel through Ten-Mile Natural Gallery": "Ten-Mile Natural Gallery",
        "No.8: Discover the Awe-inspiring Underground Palace - Yellow Dragon Cave": "Yellow Dragon Cave",
        "No.9: Hike in Zhangjiajie Grand Canyon to Return Back to Nature": "Zhangjiajie Grand Canyon",
        "No.10: Enjoy Leisurely Boat Experience on Baofeng Lake": "Baofeng Lake",
    },
}


def apply_fixes(dry_run: bool = False) -> None:
    fixed_total = 0
    removed_total = 0
    files_modified = 0

    for filename, name_map in sorted(FIXES.items()):
        filepath = DATA_DIR / filename
        if not filepath.exists():
            print(f"WARNING: {filepath} not found, skipping")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        attractions = data.get("key_attractions", [])
        new_attractions = []
        fixed = 0
        removed = 0

        for attr in attractions:
            old_name = attr["name"]
            if old_name in name_map:
                new_name = name_map[old_name]
                if new_name is None:
                    print(f"  REMOVE: \"{old_name}\"")
                    removed += 1
                    continue
                else:
                    print(f"  FIX: \"{old_name}\" -> \"{new_name}\"")
                    attr["name"] = new_name
                    fixed += 1
            new_attractions.append(attr)

        if fixed or removed:
            data["key_attractions"] = new_attractions
            files_modified += 1
            fixed_total += fixed
            removed_total += removed

            if not dry_run:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"  -> Saved {filename} ({fixed} fixed, {removed} removed)\n")
            else:
                print(f"  -> [DRY RUN] Would save {filename} ({fixed} fixed, {removed} removed)\n")

    print(f"\nDone: {fixed_total} fixed, {removed_total} removed across {files_modified} files")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    apply_fixes(dry_run=args.dry_run)
