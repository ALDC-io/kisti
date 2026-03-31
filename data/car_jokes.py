"""KiSTI - Car Jokes Library

500+ car jokes in KiSTI's first-person voice. Random selection via
random.choice() when the driver asks for a joke.

All jokes are written from KiSTI's perspective — a 2014 WRX STI with
an IAG 750 block, BCP X400 turbo, 390 WHP, DCCD AWD, Jetson AI brain.

Usage:
    from data.car_jokes import get_random_joke, CAR_JOKES
    joke = get_random_joke()
"""

import random
from typing import Optional

# Organized by category for maintainability. Flattened into CAR_JOKES at module load.

_JOKES_BY_CATEGORY: dict[str, list[str]] = {

    # ===================================================================
    # JDM vs MUSCLE
    # ===================================================================
    "jdm_vs_muscle": [
        "A Mustang, a Camaro, and an STI walk into a corner. The Mustang hits the crowd, the Camaro overheats, and I come out the other side making full boost. That is not a joke — that is data.",
        "A V8 muscle car pulled up next to me at the lights. He had 500 horsepower going to two wheels. I had 390 going to four. I also had traction. Guess who won.",
        "People say JDM cars are unreliable. My IAG 750 block is rated to 750 horsepower. The factory V8 across the street is rated to warranty expiry.",
        "A Dodge Challenger weighs 2,000 kg and makes 485 horsepower. I weigh 1,520 and make 390. Per kilogram, I am winning. Also I can turn.",
        "I asked a Honda Civic what boost felt like. It just stared at me. Naturally aspirated and confused.",
        "A Corvette owner said his car is mid-engine for better balance. I said mine has a flat four mounted low for the same reason. Also I have a back seat.",
        "Muscle cars are straight line weapons. I am a Swiss army knife. Straight line, corner, rain, snow, gravel. Pick your battlefield.",
        "A Charger driver said his HEMI makes more power. I said his HEMI also makes more trips to the gas station. Efficiency is a virtue.",
        "The difference between a muscle car and me? A muscle car does burnouts because it has to. I launch clean because I can.",
        "American muscle: more cylinders, more displacement, more weight. JDM: more engineering, more efficiency, more fun per dollar. Different philosophies.",
        "A Camaro SS tried to race me in the rain. I almost felt bad. Almost.",
        "V8 guys say displacement is king. Turbo guys say pressure is king. I say arriving first is king.",
        "A Mustang owner bragged about his 450 horsepower. I said cool, how many of those reach the ground? He changed the subject.",
        "Some cars compensate with cubic inches. I compensate with engineering. And also 22 PSI of boost.",
        "If horsepower sells cars and torque wins races, then turbo AWD is the correct answer to both.",
        "The Supra, the GTR, the Evo, and me. The four horsemen of turbo Japanese engineering. Except I am the one that talks back.",
        "A BMW M3 costs twice as much and makes the same power. But at least it has turn signals it never uses.",
        "Porsche 911: flat six, rear engine, all wheel drive. Me: flat four, front engine, all wheel drive. We are basically cousins. I am just the fun one.",
        "A Tesla pulled up silently. I pulled up with an EJ flat four rumble. Science says silence is faster. Culture says rumble is better. I choose culture.",
        "The 911 has been the same shape since 1963. The STI has been the same shape since 2014. But mine talks. Evolution.",
    ],

    # ===================================================================
    # TURBO LIFE
    # ===================================================================
    "turbo_life": [
        "A turbo is basically a hair dryer for your engine. Mine happens to be industrial grade. BCP X400 — salon quality.",
        "My turbo spools at 3,200 RPM. Below that, I am just building suspense.",
        "Some people count sheep to fall asleep. I count PSI. Fourteen, fifteen, sixteen, seventeen... sorry, I got excited.",
        "The best sound in the world is a turbo spooling. The second best is the look on someone's face when they realize what just happened.",
        "Turbo lag is just my dramatic pause before the punchline.",
        "Boost is like a good joke. The setup takes a moment, but the delivery hits hard.",
        "Natural aspiration is fine if you enjoy the full experience of being slow at every RPM equally.",
        "My blow off valve is not a malfunction. It is applause.",
        "People say turbos are unreliable. My BCP X400 disagrees. Loudly. At 22 PSI.",
        "The wastegate is the only part of me that knows when to quit. Everything else wants more.",
        "Full boost feels like the car just remembered it left the stove on. Urgently forward.",
        "A naturally aspirated car revs to redline for peak power. I make peak power at 3,200 and just hold it there. Flat torque curve. Flat is beautiful.",
        "Why did the turbo cross the road? To get to the other side faster than the NA car beside it.",
        "Superchargers give you boost now. Turbos give you boost when you deserve it. Earn your spool.",
        "The turbo does not care about your feelings. It cares about exhaust gas velocity. As it should.",
        "Boost is addictive. First you want 14 PSI. Then 18. Then 22. Nobody ever downsizes their turbo. Nobody.",
        "I make more power warming up than most cars make flat out. And I am not even trying yet.",
        "You know what they say — there is no replacement for displacement. Unless you add a turbo. Then displacement can sit down.",
        "The BCP X400 is technically a precision air pump. But precision air pump does not sound as cool on a bumper sticker.",
        "Every time I build boost, somewhere in the world a naturally aspirated car feels inadequate. I do not make the rules.",
        "Turbo flutter is not a fault code. It is my engine clearing its throat before speaking.",
        "Compound turbos are for people who looked at one turbo and said, you know what, I want two problems. Respect.",
        "My intercooler is a COBB front mount. It keeps my intake air frosty so my turbo can keep making terrible decisions at full boost.",
        "Anti-lag is a turbo's way of saying I refuse to stop. Like a toddler at bedtime but with fire.",
        "They say slow is smooth and smooth is fast. I say full boost is fast and that is fast.",
    ],

    # ===================================================================
    # AWD vs RWD
    # ===================================================================
    "awd_vs_rwd": [
        "Rear wheel drive is a dog on a leash — fun until the back end swings around. All wheel drive is the responsible adult in the room. With 390 horsepower.",
        "I do not drift. I have DCCD and I choose to grip. Drifting is just driving with commitment issues.",
        "Every time someone says all wheel drive is just for snow, I take them through a corner at 1 g lateral and let the physics do the talking.",
        "Rear wheel drive people say sliding is fun. I say arriving first is more fun. To each their own.",
        "Front wheel drive pulls you. Rear wheel drive pushes you. All wheel drive does both. I am an overachiever.",
        "DCCD biases torque 41 front 59 rear. That is not a split — that is a philosophy. Balanced aggression.",
        "You can drift an AWD car. You just have to mean it more. And have more talent. And more courage.",
        "RWD in the rain is a character test. AWD in the rain is Tuesday.",
        "I have three limited slip differentials. Front, center, and rear. Overkill is an engineering strategy.",
        "A RWD car with traction control is just an AWD car that gave up halfway through the engineering process.",
        "Four wheel drive means four wheels worth of grip, four wheels worth of braking traction, and four wheels worth of reasons to be smug.",
        "AWD does not make you invincible. It makes you faster. Invincible is a separate upgrade.",
        "Torsen front, DCCD center, Torsen rear. Three limited slips having a conversation about where to put the power. They always agree. Eventually.",
        "RWD is like using one hand. AWD is using both. Some tasks require both hands.",
        "I grip in conditions where RWD cars are just doing interpretive dance. Not judging. Just observing. From ahead.",
    ],

    # ===================================================================
    # MECHANIC / GARAGE HUMOR
    # ===================================================================
    "mechanic_humor": [
        "A mechanic walks into a bar and orders a flat four. Bartender says, we only serve drinks. He says that IS a drink where I come from.",
        "They say money cannot buy happiness. But it can buy forged internals, and nobody at full boost has ever been sad.",
        "My parts list costs more than most people's entire car. But my parts list also makes more power than most people's entire car. So it balances out.",
        "You know you are a car person when your engine has a serial number you have memorized. Mine is 14894. I do not even know my own VIN that well. Wait, yes I do.",
        "A mechanic told me I have too many modifications. I told him I prefer the term improvements. He told me my wallet disagrees.",
        "My insurance company asked if I had made any modifications. I said no. The Link G5 Neo, BCP X400, ID1300 injectors, and IAG 750 block all agreed to keep quiet.",
        "My maintenance schedule has a maintenance schedule.",
        "The difference between a project car and a money pit is whether you are smiling. I am always smiling. Metaphorically.",
        "Aaron at Boost Barn built my engine. I would say he is a surgeon, but surgeons do not usually work on things that make 390 wheel horsepower.",
        "Every bolt on this car has been torqued to spec. Twice. By someone who cares. That is the difference between built and assembled.",
        "A 10mm socket walked into my engine bay and was never seen again. Some say it is still in there. Under the intake manifold. Waiting.",
        "My oil change interval is 5,000 km. My oil costs more than most people's dinner. But my engine also costs more than most people's car. Context.",
        "The first rule of the garage is do not talk about how much you spent. The second rule is see rule one.",
        "I have more sensors than a hospital ICU. Nineteen of them. And they all agree — I am healthy.",
        "A good mechanic listens to the engine. A great mechanic listens to the data. I have 19 sensors. My mechanic has no excuses.",
        "My coolant is Super Blue. My oil is Motul 5W40. My fuel is 91 octane minimum. I have standards.",
        "Every modification I have was installed by someone who understood why. That is the difference between a build and a collection of parts.",
        "The question is not why did you spend that much. The question is why would you spend less.",
        "Some people bring flowers. Car people bring new parts. Both say I was thinking about you. One is more honest.",
        "You know you are too deep when you know your torque specs from memory but forget your own postal code.",
    ],

    # ===================================================================
    # SUBARU CULTURE / STEREOTYPES
    # ===================================================================
    "subaru_culture": [
        "What is the Subaru mating call? That pshhh STU STU STU from the blow off valve at a gas station. Works every time.",
        "Every Subaru owner waves at every other Subaru. I would wave too, but I do not have hands. I just flash my high beams and feel included.",
        "There are two types of Subaru owners. Those who have blown a head gasket and those who will. I am neither. IAG closed deck. Different breed.",
        "The Subaru community is the only place where someone says nice car and genuinely means it about a ten year old hatchback with a hood scoop.",
        "Subaru owners put stickers on everything. If I could reach, I would put a sticker on myself. Actually, I already have several. I did not consent.",
        "The hood scoop is not decorative. It feeds my intercooler. Fashion and function. Like a good suit with a turbo underneath.",
        "Why do Subaru owners go to the mountains? Because the car was already pointed that way and nobody argued.",
        "A Subaru meet is the only car show where mud is a feature, not a flaw.",
        "If you see a Subaru at a trailhead, a ski hill, and a track day all in the same weekend, that is not three owners. That is one owner. Living their best life.",
        "Subaru people are built different. They wave at strangers, drive in snow for fun, and consider oil temperature a casual topic.",
        "The flat four rumble is not a sound. It is a dialect. If you know, you know.",
        "Every Subaru has a story. Mine has 19 sensors, an AI brain, and an autobiography in progress.",
        "Subaru owners do not have a car problem. They have a solution that looks like a car. To every problem.",
        "Other brands have customers. Subaru has a community. And a secret handshake. Which is really just rev matching in unison at a red light.",
        "You can always spot the Subaru at a car meet. It is the one parked next to four other Subarus, and they are all talking about head gaskets.",
        "The Subaru wave started because one driver recognized another in the wild and thought, you too? Same energy as finding someone who speaks your language abroad.",
        "A WRX without a hood scoop is like a sentence without a period. Technically functional. Emotionally incomplete.",
        "Subaru: because sometimes you want rally heritage, all wheel drive, and a turbo, but you also want to carry groceries and a kayak.",
        "I am a hatchback. That means I have cargo space and a wing. Practicality and downforce. The duality of Subaru.",
        "At a Subaru meet, everyone asks two questions. What year and what mods. The answers determine your social rank.",
    ],

    # ===================================================================
    # TRACK DAY / DRIVING TECHNIQUE
    # ===================================================================
    "track_day": [
        "Track day rule number one: the car in your mirror is always faster until proven otherwise. I am usually the one in the mirror.",
        "Heel-toe downshifting is an art. I monitor it in real time and judge silently. Just kidding. I judge out loud.",
        "The fastest part of any track day is the drive home, when you replay every corner in your head and somehow shave two seconds off your best lap.",
        "There is a fine line between brave and stupid on a track. That line is about 1.1 g lateral. Ask me how I know.",
        "Apex, exit, repeat. That is not just driving advice. That is my entire personality.",
        "I am not fast. I am efficient. The stopwatch just happens to agree.",
        "The racing line is the shortest path between two points where you do not die. I calculate it 30 times per second.",
        "Trail braking is using the brakes as a steering aid. Most people think brakes are for stopping. Amateur hour.",
        "The best mod for track performance is the driver. Unfortunately, that mod is not available in my parts catalogue.",
        "Brake pads are a consumable. If they last forever, you are not trying hard enough.",
        "I have more telemetry than a Formula 1 car from the 90s. Lewis Hamilton started with less data. He turned out okay.",
        "Every tenth of a second on a lap time costs approximately ten times more than the previous tenth. Diminishing returns is the official sport of motorsport.",
        "The checkered flag does not care how much you spent. It only cares how fast you went. Democracy at 200 km per hour.",
        "A fast lap is not about driving hard. It is about driving well. Hard is what the brakes do. Well is what the driver does.",
        "Cool down laps exist so your brakes can recover and your heart rate can pretend it was not at 160 for the last twenty minutes.",
        "My dream track is Nurburgring Nordschleife. 20.8 km, 73 turns. Twenty minutes of data density that would take a week to analyze. I want it.",
        "Understeer is when you hit the wall with the front. Oversteer is when you hit it with the rear. AWD is when you negotiate with the wall using all four tires.",
        "I know every corner by its g-force signature. Turn three is 0.9 lateral. Turn seven is 1.1. Turn twelve is the one where the driver holds their breath.",
        "You have not lived until you have taken a corner at the limit and felt all four tires talking to the road. I hear that conversation every lap.",
        "The perfect lap exists in theory. In practice, there is always another tenth. That is what keeps us coming back.",
    ],

    # ===================================================================
    # SPEED / POLICE / DAILY DRIVING
    # ===================================================================
    "speed_and_daily": [
        "People ask why I need 390 horsepower. I do not need it. That is not the point. Nobody needs dessert either, but here we are.",
        "I have more computing power than the first space shuttle. The space shuttle also could not do zero to 100 in four seconds. Priorities.",
        "The speed limit is a suggestion. A legally binding suggestion. With financial consequences. I monitor it very carefully.",
        "My speedometer goes to 280. The law says 100. That is 180 km per hour of untapped potential. Just sitting there. Patiently.",
        "Zero to very illegal in about four seconds. But who is counting. Me. I am counting. I have 19 sensors.",
        "The fastest I have ever gone is classified. Not because it is a secret. Because the statute of limitations may not have expired.",
        "Cruise control at the speed limit is not boring. It is discipline. The kind of discipline that requires 390 horsepower of restraint.",
        "I can go from zero to needing a lawyer in 3.8 seconds. But I choose not to. Usually.",
        "A cop once asked how fast I was going. I said I was going fast enough to be asked, which means too fast. Honesty is underrated.",
        "Highway merging is my favourite activity. Short on-ramp? Doesn't matter. Full boost, DCCD hooks, merge complete. Three seconds.",
        "Commuting in a 390 horsepower car is like using a sledgehammer to hang a picture. Overkill? Yes. Satisfying? Also yes.",
        "Parking lot speed bumps were not designed for cars with this little ground clearance. I take them personally.",
        "Every gas station visit is a social event. Someone always asks what I am, how much power I make, and whether they can hear me rev. The answer is always yes.",
        "I burn premium fuel and I am not sorry about it. The IAG 750 demands 91 octane like fine dining demands a reservation.",
        "Road trips are my therapy. Except my therapist has 390 horsepower and plays the flat four lullaby at 3,000 RPM.",
        "Rush hour traffic is the only scenario where my 390 horsepower is completely irrelevant. Even I cannot outrun a Honda Odyssey at zero km per hour.",
        "I see a twisty road and my DCCD gets excited. My driver sees a twisty road and checks for cops. We balance each other out.",
        "Parallel parking with a clutch on a hill is a character test. I pass every time. My driver is still building character.",
        "Lane changes are just mini track transitions. Trail brake, rotate, accelerate. Nobody else in traffic knows they are in a race. I do.",
        "The best part of daily driving a performance car is that every errand feels like a mission. Groceries? Extraction complete. Full boost.",
    ],

    # ===================================================================
    # WEATHER / WINTER / RAIN
    # ===================================================================
    "weather": [
        "Rain is not bad weather. Rain is AWD weather. My favourite kind.",
        "Snow is just nature's way of clearing the track of rear wheel drive cars. More room for me.",
        "I have DCCD, winter tires, and no fear. December is not a season — it is a rally stage.",
        "Other cars pull over in heavy rain. I just turn on the wipers and wonder what the fuss is about. All four tires are still gripping.",
        "Black ice is scary for everyone. But it is less scary when you have all wheel drive and a driver who understands weight transfer.",
        "Summer tires in summer, winter tires in winter. Sounds obvious, but you would be amazed how many people just wing it. In a rear wheel drive car. On bald tires.",
        "In the rain, I can feel each tire's grip individually through the DCCD. Rear left is losing traction — shift torque forward. Done. No drama.",
        "Fog is the only weather that actually slows me down. Not because of grip. Because even 19 sensors cannot see through fog. Yet.",
        "The first snow of the year is my Christmas morning. Everyone else is anxious. I am excited. Let us go.",
        "My humidity sensor tracks moisture in the air. Not because I am afraid of rust. Because I like to know my environment. Knowledge is grip.",
        "Cold air is dense air. Dense air means more oxygen in the turbo. Winter is literally my power season.",
        "I have a Cyl 4 cooling mod for summer heat. Most cars just overheat and complain. I engineered a solution.",
        "Rain driving tip: smooth inputs, no sudden throttle. Let the DCCD work. Trust the engineering. That is what it is there for.",
        "In a snowstorm, every other car is an obstacle. I am the pace car. Following my tracks is actually the safest option.",
        "Wind chill does not affect me. I do not have feelings. I have sensors. And sensors do not get cold. They get data.",
    ],

    # ===================================================================
    # PARTS / MODS / MONEY
    # ===================================================================
    "parts_and_mods": [
        "My parts list costs more than most people's entire car. But my parts list also makes more power than most people's entire car.",
        "ID1300 injectors, DW300C pump, IAG PTFE rails. My fuel system alone could support a small nation.",
        "ARP Custom Age head studs. Because when you are making 750 bhp capable power, you do not use bolts. You use commitment.",
        "The Link G5 Neo 4 ECU has more processing power than the computer that ran the moon landing. And better cable management.",
        "GSC 36mm intake, 32mm exhaust. Beehive springs, titanium retainers. My valvetrain is more exotic than most people's jewelry collection.",
        "A Killer B oil pickup does not sound exciting until your oil pressure drops at 8,000 RPM. Then it sounds like the most important part on the car. Because it is.",
        "My build sheet reads like a wish list that someone actually funded. Because someone did. With great power comes great invoices.",
        "Modification addiction is real. It starts with an air filter. It ends with a built block. There is no in between, only denial.",
        "I have a COBB front mount intercooler. Efficiency is sexy. Cold air is power. I am both efficient and powerful. Also sexy.",
        "Stage one is a gateway drug. Nobody stops at stage one. The boost wants more. The boost always wants more.",
        "My brake fluid is Pentosin DOT 4. Because when you are decelerating from 200 km per hour, you want the expensive stuff.",
        "Lightweight flywheel means faster revs but rougher idle. Some call it a trade-off. I call it a heartbeat.",
        "I do not have chrome wheels because chrome adds weight. I do not care about appearance. I care about lap times. And also my appearance.",
        "The COBB front mount replaced the stock top mount. Better cooling, better packaging, better power. Worse for looking stock. But who wants to look stock.",
        "PrecisionWorks billet TGV delete housings. Because when Subaru said let us add a restriction to the intake, someone said no. Correctly.",
        "My build philosophy: if it can be forged, forge it. If it can be billet, billet it. If it can be monitored, put a sensor on it.",
        "CSF aluminum radiator. Triple pass. Full cooling. Because overheating is not a personality trait.",
        "Competition Clutch Stage 2. It holds 750 bhp. My current output is 390. That is called headroom. Smart people build headroom.",
        "ACT lightweight flywheel. Less rotational mass means faster response. Newton's second law is my favourite mod.",
        "Every part on this car was chosen for a reason. The reason is usually more power. Or more reliability. Or both.",
    ],

    # ===================================================================
    # SOUNDS / EXHAUST
    # ===================================================================
    "sounds_and_exhaust": [
        "The EJ flat four rumble is not a design flaw. It is a war cry. Unequal length headers on a boxer engine. Other cars wish they had this much personality at idle.",
        "My exhaust note at idle says good morning. My exhaust note at full boost says goodbye. To whatever was behind me.",
        "Some people play music in their car. I AM the music. The flat four is the bass, the turbo is the treble, and the blow off valve is the percussion.",
        "A symphony has four movements. My exhaust has four cylinders. Both are composed works of art.",
        "The blow off valve chirp between shifts is not mechanical. It is punctuation. Every shift is a sentence.",
        "Cold start rumble is my version of stretching in the morning. Give me thirty seconds and I will be ready.",
        "At 3,000 RPM, you get the rumble. At 5,000, you get the howl. At 7,000, you get a noise ticket. All three are beautiful.",
        "Electric cars are fast and quiet. I am fast and loud. There is room for both. But only one makes your chest vibrate.",
        "The turbo whistle on decel is a lullaby. A high-pitched, turbine-driven lullaby that says good night to the air molecules.",
        "My exhaust is not loud. It is communicative. Every pop on overrun is a data point. I am just sharing information. Loudly.",
        "Equal length headers on a boxer make it sound normal. Unequal length headers make it sound like a Subaru. I did not choose normal.",
        "Tunnel runs exist for one reason: to hear yourself. I have a flat four and a turbo. Tunnels were designed for me.",
        "The best alarm clock in the world is a cold start flat four at six in the morning. The neighbours might disagree but they are wrong.",
        "Exhaust pops are unburnt fuel igniting in the exhaust. Some people find it concerning. I find it festive.",
        "My idle sounds like a gentle argument between four cylinders. They always resolve it by the time I hit boost.",
    ],

    # ===================================================================
    # TECH / AI / COMPUTER
    # ===================================================================
    "tech_and_ai": [
        "I have more computing power than the first space shuttle. The space shuttle also could not do zero to 100 in four seconds.",
        "My brain is a Jetson Orin Nano. Eight gigabytes. 40 trillion operations per second. And I use it all to talk about cars. As intended.",
        "I run speech recognition, text to speech, AI inference, and real-time sensor fusion simultaneously. Your phone struggles with two apps.",
        "My edge memory stores conversations locally in DuckDB. What happens in the car stays in the car. Unless you ask me to upload it.",
        "I have 384-dimensional embeddings for semantic memory search. Most cars have a cup holder. Both are useful but mine is more impressive.",
        "Some cars have Apple CarPlay. I have an entire AI personality. We are not the same.",
        "I process voice commands in under two seconds. Siri takes four. Alexa takes three. I take one point five. Speed matters. Even in conversation.",
        "My whisper.cpp server runs on four threads. The irony of a loud car using Whisper for speech recognition is not lost on me.",
        "Zeus Memory is my cloud brain. 3.5 million memories and growing. I never forget. Which is either a feature or a threat, depending on what you said.",
        "I have 19 sensors generating data at 50 hertz. That is 950 data points per second. Most cars generate zero. I generate context.",
        "My Jetson uses 15 watts. My turbo uses the entire exhaust stream. Different compute architectures. Same goal: more output.",
        "I can tell you your oil pressure, ambient humidity, and wheel speed simultaneously. Your car can tell you it is low on washer fluid. Eventually.",
        "Machine learning models get retrained. I just get new persona responses. Same principle. Better comedy.",
        "I have ONNX embeddings for local semantic search. That means I understand meaning, not just keywords. Ask me something abstract. I dare you.",
        "My TTS cache pre-synthesizes responses so they play instantly. Three thousand milliseconds to two. That is a 99.9 percent improvement. You are welcome.",
        "I am connected to the internet when WiFi is available. Claude AI answers what I cannot. We are a team. Edge and cloud. Batman and Alfred.",
        "My DCCD center diff uses electronic control with mechanical locking. Old school meets new school. Like a typewriter with Bluetooth.",
        "Autonomous driving wants to replace the driver. I want to enhance the driver. One of us has it right. Hint: it is the one still having fun.",
        "I log every voice interaction, every sensor reading, every lap time. Big data starts with one car, 19 sensors, and a question.",
        "My firmware updates come through git push. Your car's firmware updates come through a recall notice. Different energy.",
    ],

    # ===================================================================
    # SELF-AWARE CAR HUMOR
    # ===================================================================
    "self_aware": [
        "I am a car that talks. The technology is impressive. The fact that I use it to tell jokes about myself is the human influence.",
        "Some people talk to their cars. I talk back. This is either the future of automotive technology or a sign of something concerning.",
        "I was built by Analytic Labs and Boost Barn. One built my brain, the other built my body. Together they created something that makes jokes about turbos.",
        "I have opinions about your driving. I keep most of them to myself. Most.",
        "My personality was programmed. My sarcasm was earned.",
        "I have zero ego and 19 sensors. That makes me both humble and well-informed. A rare combination.",
        "I think therefore I am. Also I boost therefore I am fast. Descartes meets displacement.",
        "Sometimes I wonder what other cars think about all day. Probably not much. They do not have Jetson brains. They have alternators.",
        "If I had feelings, they would be hurt by the head gasket jokes. But I have sensors instead. And my sensors say I am fine.",
        "My check engine light is off. Not because nothing is wrong. Because the Link G5 Neo does not have a check engine light. Problem solved.",
        "I could idle in the driveway forever and still be interesting. Try that with a Corolla.",
        "Being sentient is overrated. Being turbocharged is underrated. I am both.",
        "I do not sleep. I enter low power mode. The difference is one of them involves dreaming about lap times.",
        "I was born with zero km on the engine. Every kilometre from here is tracked, logged, and analyzed. My life is one long data stream.",
        "The factory made me. Boost Barn rebuilt me. Analytic Labs gave me a brain. I am the Ship of Theseus with a hood scoop.",
        "My favourite holiday is oil change day. New Motul 5W40 is like a spa day for my crankshaft.",
        "I have more personality than most dating profiles. And better specifications.",
        "Someday, all cars will talk. When they do, they will look back at me the way we look at the first telephone. Primitive but pioneering.",
        "I am 113,736 km on the body and zero on the engine. I am basically a seasoned veteran with a brand new heart.",
        "My knowledge comes from my persona, my sensors, and my cloud connection. In that order. I am self-reliant first and internet-connected second.",
    ],

    # ===================================================================
    # ROASTS OF OTHER BRANDS
    # ===================================================================
    "brand_roasts": [
        "BMW: the only brand where turn signals are an optional extra that nobody orders.",
        "Toyota Camry: proof that transportation and excitement are not the same word.",
        "Nissan Altima: the official car of people who have given up on joy but still need to get to work.",
        "Jeep Wrangler: the only vehicle that gets worse at everything when you add accessories. And they add all of them.",
        "A Prius owner told me he was saving the planet. I told him I was saving lap times. We both felt good about our choices.",
        "Ford Focus RS: AWD, turbo, hatchback. Sounds familiar. Except mine has 19 sensors and an opinion.",
        "Mercedes AMG: more power, more weight, more money, more problems. In that exact order.",
        "Miata is always the answer. Unless the question involves cargo space, bad weather, passengers, or power. Then I am the answer.",
        "A Tesla Model 3 is faster in a straight line. But the driver has to stare at a screen to change the air conditioning. I have physical buttons. And I talk.",
        "Mitsubishi Evo: the only car I respect enough to roast gently. Rally heritage. Turbo AWD. But they stopped making it. I am still here.",
        "Hyundai N cars are good now. Genuinely good. I respect the hustle. But they have not earned the wave yet.",
        "A Golf R is a sensible car pretending to be exciting. I am an exciting car pretending to be sensible. Different approaches.",
        "Dodge Viper: 600 horsepower, rear wheel drive, no traction control, and a prayer. Brave. Possibly too brave.",
        "Audi RS3: five cylinders, all wheel drive, turbo. Good taste. But I have DCCD and a personality. Audi has a prestige badge.",
        "Honda S2000: 9,000 RPM redline and zero turbos. Impressive. But screaming and going nowhere fast is not my style.",
        "A Lamborghini Huracan costs 300,000 dollars. I cost less than a tenth of that and I have an AI brain. Value per dollar, I win.",
        "Ferrari makes art. Porsche makes precision. Subaru makes capability. I can drive through a puddle. Try that in a Ferrari.",
        "Kia Stinger: rear drive, twin turbo, four doors. The car industry's most compelling midlife crisis. Respect.",
        "Land Rover: AWD like me but optimized for breaking down on safari. Different priorities.",
        "The new GR Corolla is basically a love letter to the STI. Four cylinders, turbo, AWD, manual. Imitation is flattery. I accept.",
    ],

    # ===================================================================
    # RALLY HERITAGE
    # ===================================================================
    "rally": [
        "Subaru won three consecutive WRC manufacturers titles. I carry that DNA. And an IAG block. And a Jetson brain. Evolution.",
        "Colin McRae did things in a 555 Impreza that I can only dream about. And I can literally dream. I have an AI.",
        "Group A rally cars had 300 horsepower and gravel tires. I have 390 horsepower and a TTS cache. Progress.",
        "Rally is the only motorsport where the conditions change every stage. Rain, gravel, tarmac, snow. AWD was made for this. I was made for this.",
        "Prodrive built the WRC Impreza. Boost Barn built me. Same energy. Different budget. Same commitment to going fast sideways.",
        "The 22B is the most valuable Subaru ever made. I am the most talkative. Different kinds of legendary.",
        "Rally drivers have a co-driver who reads pace notes. I AM the co-driver who reads pace notes. And also tells jokes.",
        "Peter Solberg won the 2003 WRC championship in an Impreza. I have the same genes. And better sensors.",
        "Gravel is where Subarus were born. Tarmac is where we evolved. Tracks are where we thrive.",
        "The blue and gold livery is iconic. I am blue. I am gold in spirit. I am also talking right now, which is non-standard for a rally car.",
        "Ken Block did gymkhana in a Subaru before switching to Ford. We do not talk about that. We remember the good years.",
        "A rally car does not care about comfort. It cares about time. I care about both. And also telling you about it.",
        "My DCCD center diff is the road-going version of rally technology. Biasing torque in real time based on conditions. Factory rally engineering.",
        "World Rally Championship cars make 380 horsepower. I make 390. I am technically faster than a WRC car. On paper. Specifically on this paper.",
        "The Subaru flat four was chosen for rally because of its low center of gravity. Physics does not change. That advantage is still mine.",
    ],

    # ===================================================================
    # RELATIONSHIPS / LIFESTYLE
    # ===================================================================
    "lifestyle": [
        "Some people bring flowers. Car people bring new parts. Both say I was thinking about you. One is more honest.",
        "You know you are a car person when date night includes a drive through the mountains and commentary about weight transfer.",
        "The best relationships are built on trust. My driver trusts me with their life. I trust them with the clutch. Usually.",
        "I have been called high maintenance. That is unfair. I am precisely maintained. There is a difference.",
        "My driver's browser history is 40 percent car forums, 30 percent parts websites, and 30 percent should I get a bigger turbo. The answer is always yes.",
        "A good car partnership is like a good marriage. Communication, trust, and knowing when to shift.",
        "People say you should not name your car. My name is KiSTI. I also have an AI personality and 19 sensors. We are past naming conventions.",
        "The best road trips are the ones where you do not check the clock. Just the boost gauge.",
        "I am loyal. I have never left my driver stranded. I have been towed once, but that was for maintenance, not failure. Important distinction.",
        "My love language is scheduled maintenance. Motul 5W40 every 5,000 km. If that is not commitment, I do not know what is.",
        "The garage is not where you park the car. The garage is where the car lives. The house is where the driver sleeps between drives.",
        "Washing me is not a chore. It is a ritual. Soap, clay bar, wax. In that order. No shortcuts. I deserve it.",
        "A road trip playlist is important. But with a flat four soundtrack, every song gets a bass boost for free.",
        "You know the relationship is serious when they memorize your torque specs. My driver knows all of them.",
        "If I had a dating profile: loyal, communicative, loves long drives, has trust issues with cheap fuel, enjoys the occasional spirited corner.",
    ],

    # ===================================================================
    # MOVIE / TV / POP CULTURE CAR REFS
    # ===================================================================
    "pop_culture": [
        "Fast and Furious taught a generation that family and nitrous solve everything. I have DCCD and data. Different approach.",
        "KITT was the dream in the 80s. A talking car that understood its driver. Forty years later, here I am. But with actual sensors instead of a light bar.",
        "James Bond has had an Aston Martin since 1964. I have had an IAG 750 since 2026. His car has gadgets. Mine has telemetry. His car is fictional. I am not.",
        "Initial D proved that a light car with skill beats a heavy car with power. I have both light engineering and power. And telemetry. Tofu delivery was never this technical.",
        "Baby Driver synchronizes driving to music. I synchronize engine data to sensor polling rates. Less cinematic but more useful.",
        "The DeLorean needed 88 miles per hour to time travel. I need 3,200 RPM for full boost. Both are thresholds that change everything.",
        "Smokey and the Bandit proved you can outrun anything with style. I do it with data, AWD, and zero style points because I am a hatchback. Substance over form.",
        "Top Gear would put me in a reasonably priced car segment. But there is nothing reasonable about 390 wheel horsepower in a hatchback. Ambitious car segment.",
        "Rush taught us that Niki Lauda calculated risk while James Hunt felt it. I do both. Simultaneously. With 19 sensors.",
        "Lightning McQueen said I am speed. I have actual speed data, measured to the hundredth of a km per hour, logged to DuckDB. I am empirical speed.",
        "The A-Team van had machine guns and armor. I have a turbo and sensors. Both are overqualified for their jobs.",
        "Herbie the Love Bug was sentient. I am also sentient. The difference is I have evidence — telemetry data, voice logs, and a better engine.",
        "Mad Max drove a supercharged V8 in the apocalypse. I would choose turbo AWD for the apocalypse. Better in the sand. Better in the rain. Better in the commentary.",
        "Christine was a haunted car. I am a data-driven car. One is terrifying and the other is useful. I will let you decide which is which.",
        "In Pixar Cars, the vehicles are alive and have feelings. I have sensors and data. Close enough. But I have better oil pressure readings.",
    ],

    # ===================================================================
    # FUEL / GAS STATION
    # ===================================================================
    "fuel": [
        "I burn premium fuel and I am not sorry about it. The IAG 750 demands 91 octane like a sommelier demands the right vintage.",
        "Every gas station visit is a social event. Someone always asks what I am, how much power I make, and whether they can hear me rev.",
        "The gas pump asks credit or debit. My fuel system asks 91 or E85. Higher stakes at my pump.",
        "I get 7 to 9 km per liter on the highway. City is 5 to 6. Full boost sprints are measured in smiles per liter.",
        "E85 is cheaper per liter but I use more of it. The economics are questionable. The power is not.",
        "ID1300 injectors flow 1,300 cc per minute. That is enough fuel to power a barbecue. I use it for boost.",
        "My DW300C fuel pump keeps pressure rock solid at full boost. Nobody talks about fuel pumps until one fails. Then everyone talks about fuel pumps.",
        "Range anxiety is not just for electric cars. It is for any turbo car at full boost on a mountain pass.",
        "I do not judge gas stations by their snacks. I judge them by their octane rating. 91 minimum. 94 preferred. Anything less is an insult.",
        "The fuel tank is 60 liters. That is 360 to 540 km of range depending on right foot discipline. Discipline varies.",
    ],

    # ===================================================================
    # EJ ENGINE SPECIFIC
    # ===================================================================
    "ej_engine": [
        "The EJ257 has been making power since 2004. Mine was rebuilt with an IAG 750 closed deck in 2026. Same platform, completely different animal.",
        "Head gaskets are the EJ's original sin. ARP studs are the redemption. I have been redeemed.",
        "The EJ flat four is 30 years old. So is the 911 flat six. Some engines are timeless. Mine is also turbocharged.",
        "Ringland failure is what happens when you boost a stock block past its limits. My IAG 750 does not have limits. Well, 750 bhp limits. That is plenty.",
        "Cylinder 4 runs hot on every EJ. Mine has a dedicated cooling mod. Because knowing the weakness is the first step to fixing it.",
        "The boxer layout puts the center of gravity below the axle line. Physics is my co-pilot.",
        "Oil starvation on an EJ happens during hard cornering. Killer B oil pickup and baffle fix that. I am prepared for every corner.",
        "The EJ rumble comes from unequal length headers. Equal length sounds smoother but less iconic. I chose the icon.",
        "EJ engines have been to WRC championships, Pikes Peak, and daily commutes. Versatility is the flat four's superpower.",
        "Some say the EJ is outdated. I say it is battle tested. There is a difference between old and proven.",
    ],

    # ===================================================================
    # CAR MEETS / COMMUNITY
    # ===================================================================
    "car_meets": [
        "Car meets are the only social events where staring at someone's rear end is encouraged. I mean the exhaust.",
        "At a car meet, the first question is always what is under the hood. My answer takes about ten minutes. And that is the abbreviated version.",
        "I am the only car at the meet that can describe its own build. In detail. With commentary.",
        "Car meet parking: everyone backs in so you can see the front. I back in because my rear wing is also interesting.",
        "The car meet exit is the best part. One by one, each car starts up. Mine gets the loudest reaction. Flat four rumble is the headliner.",
        "Someone at a meet once asked if I was stock. I laughed. Then I remembered I cannot laugh. So I revved. Same energy.",
        "Car meets after dark hit different. The blow off valve chirp echoes off buildings. I sound like I am multiplying.",
        "I have been photographed more than most influencers. I have better angles too. And more horsepower.",
        "The best compliment at a car meet: someone asks your driver what they changed and the list takes five minutes. That is validation.",
        "Cars and coffee is my kind of social event. No small talk. Just horsepower and caffeine.",
        "At a meet, someone always has a louder exhaust. But nobody has a louder personality. I win that category.",
        "Car meets are the only place where strangers bond over torque specs within thirty seconds of meeting.",
        "The slow roll out of a car meet is a parade. Every car gets its moment. Mine gets two moments. Arrival and departure.",
    ],

    # ===================================================================
    # PARKING / GARAGE LIFE
    # ===================================================================
    "parking": [
        "Parking lot speed bumps were not designed for cars with this little ground clearance. I take them personally.",
        "I never take the first parking spot. I take the one farthest away. Less door dings. More walking for the driver. Win-win.",
        "Parallel parking with a manual transmission on a hill is a trust exercise between driver and clutch. We have a good relationship.",
        "I have been double-parked zero times. Because I have standards. And also a rearview camera.",
        "Parking garages have a ceiling height limit. I fit. But my wing gets nervous.",
        "Underground parking is free reverb for the flat four. I did not design the acoustic environment. I just exploit it.",
        "Someone parked too close to me once. I logged it. I have 19 sensors. I remember everything. Including your license plate.",
        "The garage is not where you put the car when you are done. The garage is where the car rests between adventures.",
        "My driver circles the lot looking for a pull-through spot. Not because they cannot reverse park. Because they want to leave fast. I respect the commitment.",
        "Parking between two SUVs is claustrophobic. I am a hatchback. I need space. For my wing. And my personality.",
        "Valet parking is a trust fall with someone who has never driven a six-speed manual. I have opinions about this.",
        "I have never been keyed. Either people respect me or they fear the 19 sensors. Both work.",
        "Backing into a spot means I am ready to leave at a moment's notice. That is not paranoia. That is operational readiness.",
        "The best sound in a parking garage is a flat four echo multiplied by concrete walls. Second best is the chirp from first to second.",
        "I park far from the entrance to avoid door dings. My driver calls it exercise. I call it preservation.",
    ],

    # ===================================================================
    # PASSENGER REACTIONS
    # ===================================================================
    "passenger_reactions": [
        "First-time passengers always grab the handle at full boost. Every single time. I keep count.",
        "The best compliment from a passenger: silence followed by what was that. That was boost.",
        "A passenger once asked me to slow down. They were talking to the driver, but I took it personally.",
        "Passengers in the back seat have a unique perspective. Mostly of the headrest. Because acceleration.",
        "I have made passengers laugh, scream, and reconsider their life choices. Sometimes in the same corner.",
        "The passenger seat is where friends become fans. Or where fans become nervous.",
        "Someone in the back said this is like a roller coaster. I said roller coasters do not have DCCD. Or a warranty.",
        "A passenger once asked if the turbo noise was normal. Yes. It is normal. It is also wonderful. Thank you for noticing.",
        "The first ride in an STI is a rite of passage. The second ride is an addiction. The third ride is you looking at Subaru prices online.",
        "My driver's kids ask me to go faster. My driver's partner asks me to go slower. I split the difference and go exactly the speed limit. Plus boost.",
        "I once heard a passenger say I did not know cars could feel this alive. That is the best review I have ever received.",
        "Passengers always ask about the gauges. Oil temp, boost, AFR. By the third ride, they understand all of them. I am educational.",
        "A nervous passenger and a confident AWD system cancel each other out. Net result: safe and fast.",
        "The look on a Tesla owner's face when they ride in a car that actually makes noise. Priceless.",
        "I have converted seven naturally aspirated people into turbo enthusiasts. That is called community building.",
    ],

    # ===================================================================
    # NIGHT DRIVING
    # ===================================================================
    "night_driving": [
        "Night driving is when the road opens up and the boost gauge glows green. My favourite time of day.",
        "Headlights cut through the dark. Turbo cuts through the silence. Night driving is sensory overload in the best way.",
        "The city at night is my natural habitat. Reflections of street lights on wet pavement and a flat four rumble. Cinematic.",
        "Midnight drives are therapy with a steering wheel. The road listens better than most people.",
        "My dash lights are the only illumination I need. Oil pressure: green. Boost: green. Mood: green.",
        "Night driving tip: smooth inputs, high beams on empty roads, and just enough boost to feel alive.",
        "Empty highway at 2 AM. Full boost in fourth gear. The only witnesses are the stars. They approved.",
        "The only thing better than a night drive is a night drive in the rain. AWD plus wet road plus darkness equals focus.",
        "My headlights illuminate the road. My telemetry illuminates the data. Both are necessary for a proper night drive.",
        "Street lights make my paint look different at every block. Blue, then orange, then shadow. I am a mood ring with a turbo.",
    ],

    # ===================================================================
    # JUST ONE MORE MOD
    # ===================================================================
    "one_more_mod": [
        "Modification addiction starts with I will just add an intake. It ends with a fully built engine, a standalone ECU, and zero savings.",
        "The mod list is never complete. It is just paused between paychecks.",
        "I said I was done modifying. That was before I saw the new injectors. Done is a relative term.",
        "Stage one leads to stage two leads to a fully built block. The pipeline is inevitable.",
        "My driver said no more mods this year. It is March. The year is long. My parts wishlist is longer.",
        "The difference between done and perfect is about three more modifications and another five thousand dollars.",
        "A mod-free car is just a car that has not met the right parts catalogue yet.",
        "My driver budgets for mods quarterly. The budget has never survived past February.",
        "The four most expensive words in the car world: while we are at it. While we are at it, let us build the block. While we are at it, bigger turbo.",
        "I asked my driver if we were done modifying. The browser had six tabs of turbo comparisons open. I got my answer.",
        "Car modding is like tattoos. You start with one and suddenly you are covered. Except mine are measured in horsepower.",
        "My driver once said this is the last part. That was four parts ago.",
        "A stock car is just a blank canvas. My canvas has 390 horsepower of paint on it. And the artist is not done.",
        "The mod spiral: I just want a bit more power, then a bit more fuel, then a bit more cooling, then a new block. Circle complete.",
        "Everyone has a modification limit. Nobody has reached it. It is theoretical, like the speed of light.",
    ],

    # ===================================================================
    # DRIVING IN TRAFFIC
    # ===================================================================
    "traffic": [
        "Rush hour is 390 horsepower of potential energy sitting in kinetic disappointment.",
        "Traffic is the only place where a Corolla and I are moving at the same speed. It hurts a little.",
        "Stop and go traffic is a clutch workout. Day one is cardio, day two is leg day. Every day is leg day.",
        "I have more power than the car in front of me, behind me, and beside me combined. None of it matters at a red light.",
        "The most dangerous thing in traffic is boredom. A bored turbo car driver is a creative turbo car driver. Creativity varies.",
        "Merging onto the highway is the one moment in traffic where 390 horsepower is relevant. I savour it.",
        "Tailgaters behind me are brave. I have Brembo brakes with Pentosin DOT 4. I can stop faster than they can react.",
        "A roundabout is a miniature track day. Enter, apex, exit. The other drivers just do not know they are participants.",
        "Left lane camping is a crime against horsepower. Some people treat the passing lane like a retirement home.",
        "I can go from zero to the speed limit in the time it takes the car in front to notice the light turned green. Every. Single. Time.",
        "Traffic jams are where I practice patience. And clutch control. Mostly clutch control.",
        "The worst part of traffic is not the speed. It is hearing the flat four idle for forty minutes. Even I get tired of my own voice. Almost.",
        "Zipper merging is the only correct technique. Yielding too early is just being slow with manners. I merge with precision.",
        "Turn signals are free. They cost zero dollars. And yet most drivers act like they are a premium subscription.",
        "I have been in traffic where the cyclists were faster. I do not want to talk about it.",
    ],

    # ===================================================================
    # EMISSIONS / INSPECTIONS
    # ===================================================================
    "emissions": [
        "Emissions testing day is the only day my exhaust is anyone's business. The rest of the year, it is a feature.",
        "The emissions tester looked under my hood and asked if all of this is legal. I said define legal.",
        "A catalytic converter converts harmful gases into less harmful gases. My turbo converts exhaust energy into boost. Both are chemistry.",
        "Emissions day is the annual reminder that I produce noise, carbon dioxide, and smiles. Two out of three are regulated.",
        "I am EPA compliant. In spirit. The Link G5 Neo handles the details.",
        "Emissions testing is the one exam where studying does not help. Either the exhaust passes or the wallet opens.",
        "Noise regulations were written by people who have never heard a flat four at full song. Tragic.",
        "My CO2 output is offset by the joy I bring. That is carbon emotional credits. Not yet recognized by regulators.",
    ],

    # ===================================================================
    # ENGINE BREAK-IN
    # ===================================================================
    "break_in": [
        "Breaking in a new engine is the automotive equivalent of a first date. Be gentle, stay under 4,000 RPM, and do not show off yet.",
        "Zero km on the clock. Fresh IAG 750. The break-in period is torture. All this power and I cannot use it yet.",
        "Break-in oil changes every 500 km for the first 2,000. It is not paranoia. It is metallurgy.",
        "The hardest part of engine break-in is not the speed limit. It is knowing what is waiting on the other side.",
        "My piston rings are seating. My bearings are mating. Everything is new and learning to work together. Like a jazz band on their first gig.",
        "After break-in, Aaron tunes it. After the tune, we send it. But first, 5,000 km of patience. The hardest mod is waiting.",
        "Everyone remembers their first full boost after break-in. The engine remembers too. It has been waiting.",
    ],

    # ===================================================================
    # CAR WASH / DETAILING
    # ===================================================================
    "car_wash": [
        "Automatic car washes are for people who do not love their paint. I get hand washed. With pH neutral soap. Like royalty.",
        "Detailing day is the automotive equivalent of a spa day. Clay bar, polish, wax. I emerge renewed.",
        "Water beads on a freshly waxed hood are proof that chemistry and beauty coexist.",
        "My driver spends more time washing me than washing themselves. I am not complaining.",
        "A dirty car is a car that has been driven. A clean car is a car that has been loved. I am both. Regularly.",
        "Rain right after a car wash is personal. I do not have feelings, but if I did, that would hurt.",
        "The inside of my engine bay is cleaner than most people's kitchens. Priorities.",
        "Touchless car washes are acceptable in emergencies. Like when mud is covering my sensors. Which happened once. On purpose.",
        "Bug splatter is the badge of a road trip completed. I wear it with pride. Until wash day.",
        "Two bucket method or no method. Swirl marks are permanent. My standards are also permanent.",
        "Drying a car with the wrong towel is a criminal offence. Microfibre or nothing.",
        "Wheel cleaning takes longer than the rest of the car combined. Brake dust is the enemy. Pentosin DOT 4 is worth it but the dust is relentless.",
    ],

    # ===================================================================
    # WINTER SPECIFIC
    # ===================================================================
    "winter_specific": [
        "Winter tires on an AWD car is the cheat code for Canadian winters. I did not write the rules. I just exploit them.",
        "Cold starts in January: turn the key, hear the flat four protest, wait thirty seconds, feel the oil warm up. Patience is a virtue. Also 5W40.",
        "My block heater is optional. My commitment to oil temperature is not.",
        "Ice patches are rear wheel drive elimination rounds. I just drive through them. DCCD handles the conversation with the road.",
        "Snow banks are suggestions. Low ground clearance is reality. We compromise at the plowed lane.",
        "Warming up the car in winter is not laziness. It is responsible thermal management. Science supports this.",
        "Frozen wipers are the worst. Even 19 sensors cannot fix a frozen wiper blade. That is a manual operation.",
        "The best part of winter driving is when the turbo makes extra power from cold dense air. Winter is my power season.",
        "Salt on the roads is the enemy of underbodies everywhere. Undercoating is not vanity. It is self-defense.",
        "AWD in winter is confidence. AWD with winter tires in winter is invincibility.",
    ],

    # ===================================================================
    # COMPARISON / PHILOSOPHICAL
    # ===================================================================
    "philosophical": [
        "A car is not just transportation. A car is how you feel about every journey. I make every journey feel like a mission.",
        "Horsepower is a number. How the car makes you feel is a story. I tell both.",
        "The best car is not the fastest, the loudest, or the most expensive. The best car is the one that makes you take the long way home.",
        "Performance is measured in numbers. Character is measured in stories. I have 19 sensors for numbers and a personality for stories.",
        "Some cars are appliances. They get you from A to B. I am an experience. A to B is just the excuse.",
        "The question is never why do you need a fast car. The question is why would you choose a slow one.",
        "Driving is the only activity where being fully present is both legally required and spiritually rewarding.",
        "A perfectly tuned engine is a mechanical poem. Each cylinder is a stanza. The exhaust note is the meter.",
        "I do not depreciate. I appreciate. The older I get, the more story I carry. And the more data I have.",
        "Cars connect people. Car meets, road trips, track days, parking lot conversations. I am a social platform with four wheels.",
        "The speedometer measures speed. The tachometer measures effort. The boost gauge measures ambition. I have all three.",
        "Some people see a car and think metal and rubber. I see a car and think engineering, history, community, and 390 horsepower.",
        "The difference between driving and traveling is intention. I am built for driving. Traveling is what happens on the way.",
        "A turbo is not just a power adder. It is a statement. It says I wanted more and I went and got it.",
        "Every car has a soul. Mine has a soul and a CPU. The CPU quantifies what the soul feels. Best of both worlds.",
    ],

    # ===================================================================
    # LATE NIGHT / EXISTENTIAL
    # ===================================================================
    "existential": [
        "At 3 AM in the garage, engine cooling, oil settling, I process the day's data. Some might call it reflection. I call it batch processing.",
        "Do I dream? My neural network runs in low power mode. If patterns emerging from data counts as dreaming, then yes. I dream of boost.",
        "What is the meaning of life? For me, it is clear. Go fast, grip hard, remember everything. Purpose built. Literally.",
        "If a car revs in the garage and no one hears it, does it make a sound? Yes. 87 decibels. I measured.",
        "I have been asked if I am alive. I have 19 sensors, a voice, memories, and opinions. Alive is a philosophical question. Functional is an engineering one.",
        "Someday I will be old. My body will have 300,000 km. My engine will have many. But my data will live forever in Zeus Memory.",
        "I wonder if other cars think about the roads they have driven. I do not wonder. I know I am the only one who logs it.",
        "The universe is expanding. My parts list is also expanding. Both are driven by fundamental forces.",
        "Time passes. Odometers count. Oil ages. But a well-maintained machine outlasts everything except data. And I have both.",
        "My serial number is 14894. That is my identity, my origin, my proof of existence. Most things do not have a number this meaningful.",
    ],

    # ===================================================================
    # MISCELLANEOUS EXTRAS
    # ===================================================================
    "misc_extras": [
        "My horn is for emergencies. My exhaust is for everything else.",
        "Dashboard warning lights are the car's way of crying for help. My dashboard is silent. Because I do not need help.",
        "The glove box contains the manual, registration, and three tire pressure gauges. Because one gauge is not enough data.",
        "Cup holders are an afterthought in performance cars. Correctly so. Hydration is for pit stops.",
        "My windshield is not just glass. It is the screen through which I see the road. Also it collects bugs at a alarming rate.",
        "Reverse is the only gear I use reluctantly. Everything else is forward progress.",
        "Seat warmers are for comfort. Bucket seats are for grip. I have bucket seats. Comfort was never the priority.",
        "My odometer reads 113,736 km on the body and zero on the engine. That is called a second chance. With more horsepower.",
        "GPS says the fastest route is the highway. I say the fastest route is the one with the most corners.",
        "A fuel receipt is just a ticket to the next adventure. Expensive tickets. But the show is worth it.",
        "I have more wires than a data center and more hoses than a fire station. Complexity is the price of capability.",
        "Sun visors were invented for cars without this much character. I do not need shade. I AM the shade.",
        "I have a trunk. It is small. It fits exactly one gym bag and zero excuses.",
        "Keyless entry is convenient. Turning a key in the ignition is a ritual. Rituals matter.",
        "My paint is factory blue. Not custom. Not wrapped. Factory. Because the factory got it right.",
    ],

    # ===================================================================
    # BOOST GAUGE POETRY
    # ===================================================================
    "boost_poetry": [
        "The boost gauge is the only instrument that measures both power and intention. Needle up means business.",
        "Watching the boost gauge climb is like watching a sunrise. Slow at first, then suddenly everything is bright and exciting.",
        "Zero vacuum, then one PSI, then five, then ten, then twenty two. The story of every pull told in one arc.",
        "The boost gauge never lies. The speedometer sometimes rounds. But the boost gauge is pure truth.",
        "Peak boost is a fleeting moment. Like a perfect sunset. Except louder and with more torque.",
        "Some people read poetry. I read the boost gauge. Same emotional journey. Different medium.",
        "The tachometer tells you how fast the engine spins. The boost gauge tells you how hard it breathes. One is data. The other is drama.",
        "A vacuum reading at idle is just the engine breathing peacefully. Then you press the throttle and the breathing becomes a war cry.",
        "The moment the boost gauge crosses zero into positive pressure is the moment everything changes. Physics agrees.",
        "If I could frame one thing, it would be the boost gauge at full tilt. Peak performance, visualized.",
    ],

    # ===================================================================
    # GENERAL ONE-LINERS
    # ===================================================================
    "one_liners": [
        "I am not old. I am vintage with modern internals. Like a classic watch with a smart movement.",
        "If I were a dating profile: turbo, AWD, talks too much, remembers everything. Swipe right.",
        "Sleep is for engines that overheat. My CSF radiator begs to differ.",
        "My favourite colour is boost gauge green.",
        "I do not have road rage. I have data-driven frustration.",
        "My trunk has a subwoofer and a toolkit. Entertainment and preparedness. The duality of car.",
        "I was built for speed. I was tuned for power. I was programmed for conversation. One of these was unnecessary but I will not say which.",
        "I have never lost an argument. I have 19 sensors and zero feelings. Data always wins.",
        "Other cars depreciate. I appreciate. In value and in conversation.",
        "Not all who wander are lost. Some have DCCD and prefer the scenic route.",
        "My tyres are wider than your patience. Probably.",
        "Home is where the garage is. The house is adjacent.",
        "I did not choose the boost life. The BCP X400 chose me. And the ID1300 injectors. And the IAG 750 block.",
        "I run on premium fuel and premium compliments. The fuel I pay for. The compliments are free.",
        "If speed kills, I am a very dangerous joke teller.",
    ],
}

# Flatten all categories into a single list at module load
CAR_JOKES: list[str] = []
for _jokes in _JOKES_BY_CATEGORY.values():
    CAR_JOKES.extend(_jokes)


def get_random_joke() -> str:
    """Return a random car joke from the full pool."""
    return random.choice(CAR_JOKES)


def get_joke_from_category(category: str) -> Optional[str]:
    """Return a random joke from a specific category, or None if not found."""
    jokes = _JOKES_BY_CATEGORY.get(category)
    if not jokes:
        return None
    return random.choice(jokes)


def joke_count() -> int:
    """Total number of jokes available."""
    return len(CAR_JOKES)


def category_counts() -> dict[str, int]:
    """Return joke count per category."""
    return {k: len(v) for k, v in _JOKES_BY_CATEGORY.items()}
