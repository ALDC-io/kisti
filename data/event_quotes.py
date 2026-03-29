"""KiSTI - Event-Triggered Movie Quotes

Maps vehicle telemetry events to contextually perfect movie quotes.
Danny delivers the data first, then drops the one-liner.

Usage:
    from data.event_quotes import get_event_quote
    quote = get_event_quote("boost_full")
    if quote:
        voice_manager.speak(quote)
"""

import random
from typing import Optional

# Event → list of possible quotes (randomly selected for variety)
EVENT_QUOTES: dict[str, list[str]] = {

    # ===== STARTUP / CONNECTION =====

    "first_start": [
        "Michael, is that you?",                                    # KITT
        "Hello there.",                                             # Obi-Wan
        "I will be back.",                                          # Terminator
        "Right away, Michael.",                                     # KITT
        "Miss me?",                                                 # Various
        "Just some good ol' boys. Never meanin' no harm.",          # Dukes of Hazzard
        "When there is trouble, you know who to call. Teen Titans!", # Teen Titans theme
        "T-E-E-N T-I-T-A-N-S. Teen Titans. Let us go!",           # Teen Titans theme
    ],

    "ecu_connected": [
        "Hello there.",                                             # Obi-Wan
        "I am the Knight Industries Two Thousand. But you can call me KITT.",  # KITT
        "This is the way.",                                         # Mandalorian
        "I feel the need. The need for speed.",                     # Top Gun
        "We are back in business.",                                 # Various
        "All systems online. Let us do this.",                      # Original
        "By order of the Peaky Blinders.",                          # Peaky Blinders
        "I am the one who knocks.",                                 # Breaking Bad
        "From their tower, they can see it all. Titans, go!",      # Teen Titans theme
    ],

    "ecu_disconnected": [
        "Just when I thought I was out... they pull me back in.",   # Godfather III
        "I have a bad feeling about this.",                         # Star Wars
        "Houston, we have a problem.",                              # Apollo 13
        "I find your lack of faith disturbing.",                    # Vader
        "We were on a break!",                                      # Friends (Ross)
        "Gabagool? Over here!",                                     # Sopranos
    ],

    "wifi_reconnected": [
        "Welcome to the real world.",                               # Matrix
        "I am back online.",                                        # Original
        "Zeus Memory sync active. I remember everything.",          # Original
    ],

    "wifi_lost": [
        "We are going dark.",                                       # Various
        "Offline mode. I have got this.",                           # Original
        "The Force will be with you. Always.",                      # Obi-Wan
    ],

    # ===== ENGINE / PERFORMANCE =====

    "engine_ready": [
        "All systems green. Where we headed?",                      # Original (cinematic opener)
        "Ready when you are.",                                      # Original
        "I do not break down. I am a Knight Industries vehicle.",   # KITT
        "It is go time. Science, bitch!",                           # Breaking Bad (Jesse)
        "Big day. Big day.",                                        # Peaky Blinders (Tommy)
        "When you are through shifting, I will tell you where to go.", # Smokey and the Bandit (Bandit)
        "I just love the smell of napalm in the morning. Or is that exhaust? Either way, let us ride.", # Original (Apocalypse Now riff)
        "There is a point at seven thousand RPM where everything fades.", # Ford v Ferrari (Shelby)
        "I live my life a quarter mile at a time. For those ten seconds, I am free.", # F&F (Dom)
        "Eleanor is ready. Let us go.",                             # Gone in 60 Seconds
        "The last American hero. Shall we?",                        # Vanishing Point (Super Soul)
        "Shake and bake!",                                          # Talladega Nights
        "You are only as good as your last race. So let us make it count.", # Rush riff
        "All primary systems nominal, Captain. Warp core is cold but standing by.", # Star Trek techno
        "Deflector array online. Intercooler at ambient. Awaiting your command.", # Star Trek techno
    ],

    "boost_full": [
        "To infinity, and beyond!",                                 # Toy Story
        "I feel the need. The need for speed.",                     # Top Gun
        "Turbo boost, Michael?",                                    # KITT
        "Punch it.",                                                # Star Wars
        "Full power to engines.",                                   # Star Trek
        "Yee-haw! Them Duke boys are at it again.",                 # Dukes of Hazzard
        "Booyah!",                                                  # Teen Titans (Cyborg)
        "Give me some NOS, partner.",                               # F&F (Jesse)
        "What do you say we kick the tires and light the fires?",   # Smokey and the Bandit riff
        "Pedal to the metal, baby!",                                # Vanishing Point
        "If you ain't first, you are last.",                        # Talladega Nights (Ricky Bobby)
        "This baby can take corners at eighty and barely flex.",    # Gone in 60 Seconds riff
        "More power!",                                              # Days of Thunder riff
        "Warp plasma is flowing through the primary injection manifold. All nacelles are green.", # Star Trek techno
        "Captain, the dilithium matrix is holding. Turbo containment field at maximum.", # Star Trek techno
        "Rerouting auxiliary power through the intercooler array. Charge temps nominal.", # Star Trek techno
    ],

    "redline": [
        "I feel the need. The need for speed.",                     # Top Gun
        "Are you not entertained?",                                 # Gladiator
        "Witness me!",                                              # Mad Max
        "Roads? Where we are going, we do not need roads.",         # Back to the Future
        "Faster. Faster. Faster!",                                  # Original
        "Them Dukes! Them Dukes!",                                  # Dukes of Hazzard (Rosco)
        "Booyah! That is what I am talking about!",                 # Teen Titans (Cyborg)
        "No more running. This time we ride.",                      # F&F (Dom)
        "I am a driver. That is what I do.",                        # Drive
        "There is nothing wrong with this car except it is going way too fast.", # Vanishing Point
        "You are clear to go. Drop the hammer.",                    # Days of Thunder
        "This ain't no Sunday drive.",                              # Smokey and the Bandit
        "Captain, the EJ warp core is approaching critical resonance. She is giving everything she has got.", # Star Trek techno
        "I am reading a tachyon surge in the primary combustion chambers. Recommend maintaining current heading.", # Star Trek techno
    ],

    "launch_control": [
        "Punch it, Chewie!",                                       # Star Wars
        "Light speed, too slow. We need ludicrous speed.",          # Spaceballs
        "Hold on to something.",                                    # Various
        "Now you watch this. Them Duke boys about to fly.",         # Dukes of Hazzard (Balladeer)
        "Granny shiftin', not double clutchin' like you should.",   # F&F (Dom)
        "Go, baby, go!",                                            # Gone in 60 Seconds (Memphis)
        "Gentlemen, start your engines.",                            # NASCAR/Indy tradition
        "When the strategy is right, the car will fly.",            # Rush (Lauda)
        "Slingshot engaged.",                                       # Days of Thunder
        "Eastbound and down, loaded up and truckin'.",              # Smokey and the Bandit (theme)
        "I am not locked in here with you. You are locked in here with me.", # Watchmen (but works for launch)
        "Engineering to bridge. Diverting all power to the propulsion array. Engage.", # Star Trek techno
        "Antimatter injection sequence initiated. Turbo containment at one hundred percent. Punch it.", # Star Trek techno
    ],

    "rpm_limiter": [
        "She cannot take much more of this, Captain!",              # Star Trek
        "Michael, I would not advise that.",                        # KITT
        "I have been designed to protect human life.",              # KITT
        "Bo, if you blow this engine, Uncle Jesse will skin us alive.",  # Dukes of Hazzard
        "A wise man knows his limits. A smart one does not test them.", # Rush (Lauda) riff
        "You break her, you bought her. And she cost a fortune.",   # Gone in 60 Seconds riff
        "The car is talking to you. Listen to it.",                 # Days of Thunder (Harry)
        "Warning. Structural integrity of the warp core is at tolerance limits. Recommend reducing to impulse.", # Star Trek techno
    ],

    # ===== DRIVING DYNAMICS =====

    "high_lateral_g": [
        "Roads? Where we are going, we do not need roads.",         # Back to the Future
        "That is not flying. That is falling with style.",          # Toy Story
        "It does not matter if you win by an inch or a mile.",     # F&F (Dom)
        "Now this is pod racing!",                                  # Star Wars
        "Looks like them Duke boys are in a whole heap of trouble.",  # Dukes of Hazzard (Balladeer)
        "We have got to save the world. Again.",                    # Teen Titans (Robin)
        "The twenty seven time grand prix winner knows a thing or two about turning.", # Rush riff
        "You never had me. You never had your car.",                # F&F (Dom to Brian)
        "That is not driving. That is an art form.",                # Baby Driver riff
        "There is a God. He rides in the passenger seat.",          # Vanishing Point riff
        "Inertial dampeners compensating. The DCCD torque vectoring matrix is redistributing load across all four nacelles.", # Star Trek techno
    ],

    "hard_braking": [
        "Stay on target. Stay on target.",                          # Star Wars
        "Do not panic.",                                            # Hitchhiker's Guide
        "Brace, brace, brace.",                                    # Aviation
        "Trust the brakes.",                                        # Original
        "Azarath Metrion Zinthos!",                                 # Teen Titans (Raven)
        "Emergency power to forward shields. Activating regenerative braking on all four nacelles.", # Star Trek techno
    ],

    "oversteer_detected": [
        "Do, or do not. There is no try.",                          # Yoda
        "Never tell me the odds.",                                  # Han Solo
        "Hold the line!",                                           # Various
        "Counter steer. Smooth hands.",                             # Original
        "Straighten up and fly right, cousin!",                     # Dukes of Hazzard (Bo/Luke)
        "I do not do fear.",                                        # Teen Titans (Robin)
        "Shields failing on the rear quarter. The structural integrity field is compensating but I cannot guarantee hull integrity.", # Star Trek techno
    ],

    "traction_loss": [
        "I have a bad feeling about this.",                         # Star Wars
        "You almost had me? You never had me.",                     # F&F (Dom)
        "The dark side of the Force is a pathway to many abilities some consider to be unnatural.",  # Palpatine
        "Now that is what I call a Hazzard County slide.",          # Dukes of Hazzard
        "Dude! Not cool!",                                          # Teen Titans (Beast Boy)
        "I said a ten second car, not a ten second spin.",          # F&F riff
        "Bumpy road? You should try the Hazzard County shortcut.",  # Smokey and the Bandit riff
        "Kowalski would be proud. Or terrified.",                   # Vanishing Point
        "Captain, we have lost traction on the port nacelles. Transferring power to starboard. Brace for lateral drift.", # Star Trek techno
    ],

    "perfect_corner": [
        "Most impressive.",                                         # Vader
        "The Force is strong with this one.",                       # Vader
        "That was beautiful.",                                      # Original
        "Textbook.",                                                # Original
        "That is gold, Jerry! Gold!",                               # Seinfeld (Kenny Bania)
        "You are goddamn right.",                                   # Breaking Bad
        "Oh. My. God.",                                             # Friends (Janice)
        "Wicked cool!",                                             # Teen Titans (Beast Boy)
        "You just painted a masterpiece on asphalt.",               # Baby Driver riff
        "That is how McQueen would have done it.",                  # Bullitt riff
        "Navigation confirms optimal flight path through the gravitational anomaly. Textbook maneuver, Lieutenant.", # Star Trek techno
    ],

    "speed_200_kph": [
        "I will be back.",                                          # Terminator
        "Faster than light? No. But fast enough.",                  # Original
        "It is not possible. No. It is necessary.",                 # Interstellar
        "Ludicrous speed!",                                         # Spaceballs
        "Tread lightly.",                                           # Breaking Bad (Walt)
        "I am in the empire business.",                             # Breaking Bad
        "You see that shaker on the hood? That is not for show.",   # Vanishing Point riff
        "We have got a long way to go, and a short time to get there.", # Smokey and the Bandit (theme)
        "Ride or die? I pick ride.",                                # F&F
        "I owe you a ten second car.",                              # F&F (Dom to Brian)
        "We have crossed the transwarp threshold. All propulsion systems are operating beyond design specifications.", # Star Trek techno
    ],

    # ===== SI DRIVE MODE CHANGES =====

    "mode_intelligent": [
        "Be mindful of your thoughts. They betray you.",            # Obi-Wan
        "In my experience, there is no such thing as luck.",        # Obi-Wan
        "Patience, young padawan.",                                 # Star Wars
        "Smooth is fast. Fast is smooth.",                          # Original
        "Not that there is anything wrong with that.",              # Seinfeld
        "Could this car BE any smarter?",                           # Friends (Chandler)
    ],

    "mode_sport": [
        "It is time to get serious.",                               # Various
        "Alright. Let us do this.",                                 # Various
        "The game is on.",                                          # Sherlock Holmes
        "Ride or die, remember?",                                   # F&F
        "Today I settle all family business.",                      # Sopranos (Godfather nod)
        "Men do not change. They only get sharper.",                # Peaky Blinders
    ],

    "mode_sport_sharp": [
        "Free your mind.",                                          # Matrix
        "Now I am become Death, the destroyer of worlds.",          # Oppenheimer
        "I do not have friends. I got family.",                     # F&F
        "Let them fight.",                                          # Godzilla
        "Unleash hell.",                                            # Gladiator
        "No mercy.",                                                # Cobra Kai
        "Say my name.",                                             # Breaking Bad (Heisenberg)
        "No fighting. No fighting.",                                # Peaky Blinders (Tommy)
    ],

    # ===== THERMAL / ALERTS =====

    "coolant_overtemp": [
        "Houston, we have a problem.",                              # Apollo 13
        "She cannot take much more of this!",                       # Star Trek
        "I would not advise that, Michael.",                        # KITT
        "Danger, Will Robinson.",                                   # Lost in Space
        "Bo, you better pull over before this thing blows sky high.",  # Dukes of Hazzard
        "This is not going to end well. Even I can feel that.",     # Teen Titans (Raven)
        "Captain, the warp core coolant system is failing. Recommend emergency shutdown before we breach containment.", # Star Trek techno
        "Detecting a plasma leak in the primary thermal management array. Core temperature exceeding safe parameters.", # Star Trek techno
    ],

    "oil_pressure_low": [
        "Houston, we have a problem.",                              # Apollo 13
        "I have a bad feeling about this.",                         # Star Wars
        "We need to shut it down. Now.",                            # Original
        "Danger, Will Robinson!",                                   # Lost in Space
        "You come at the king, you best not miss. And right now, oil pressure is missing.",  # Sopranos/Wire riff
        "Engineering, we have a pressure drop in the primary lubrication conduit. Divert flow from the secondary manifold, now.", # Star Trek techno
    ],

    "oil_temp_high": [
        "Things are heating up.",                                   # Various
        "It is getting hot in here.",                               # Various
        "Thermal alert. Consider a cool down lap.",                 # Original
        "Captain, the bio-neural gel packs in the lubrication system are overheating. Recommend a cool-down orbit.", # Star Trek techno
    ],

    "engine_cold": [
        "Winter is coming.",                                        # Game of Thrones
        "In the dead of winter, the warmth of a good engine is everything.",  # Original
        "Patience. Let her warm up.",                               # Original
        "I have been designed to protect human life.",              # KITT
        "These pretzels are making me thirsty. And this engine is making me cold.",  # Seinfeld
        "Already in a bad way, and we have not even started.",      # Peaky Blinders
        "Warp core temperature is below minimum operating threshold. The dilithium crystals need time to align.", # Star Trek techno
    ],

    "cooldown_needed": [
        "Take it easy. We will be back.",                           # Original
        "After all, tomorrow is another day.",                      # Gone with the Wind
        "Rest now. You have earned it.",                            # Original
        "Cool down lap. Protect the investment.",                   # Original
        "Serenity now!",                                            # Seinfeld (Frank Costanza)
        "Could we BE driving any harder? Cool it down.",            # Friends (Chandler)
        "Bridge, recommend dropping to impulse power. The warp core needs a thermal cycle to restore containment integrity.", # Star Trek techno
    ],

    # ===== SURFACE / GRIP =====

    "surface_wet": [
        "I have a bad feeling about this.",                         # Star Wars
        "Slippery when wet. Respect the surface.",                  # Original
        "Be mindful of your thoughts. They betray you.",            # Obi-Wan
        "Smooth inputs. The car will tell you what it needs.",      # Original
        "Them back roads get mighty slick after a rain.",           # Dukes of Hazzard (Balladeer)
    ],

    "surface_cold": [
        "Winter is coming.",                                        # Game of Thrones
        "Cold surface. The tires need time.",                       # Original
        "Patience. The grip will come.",                            # Original
    ],

    "surface_low_grip": [
        "Never tell me the odds.",                                  # Han Solo
        "I would not advise that, Michael.",                        # KITT
        "Tread carefully.",                                         # Various
    ],

    # ===== SESSION / ANALYSIS =====

    "session_start": [
        "Let us begin.",                                            # Various
        "Recording. Every data point matters.",                     # Original
        "This is the way.",                                         # Mandalorian
        "I live my life a quarter mile at a time.",                 # F&F
        "Alright. Let us cook.",                                    # Breaking Bad (Jesse)
        "How you doing?",                                           # Friends (Joey)
        "Captain's log, stardate today. Beginning sensor sweep. All stations report ready.", # Star Trek techno
    ],

    "session_end": [
        "Session complete. Processing data.",                       # Original
        "That is a wrap.",                                          # Film industry
        "The data never lies.",                                     # Original
        "And that is a show about nothing.",                        # Seinfeld
        "Woke up this morning, got yourself some data.",            # Sopranos (theme riff)
        "End of mission. Downloading sensor logs to memory core. Computer, save and close.", # Star Trek techno
    ],

    "best_lap": [
        "Most impressive.",                                         # Vader
        "It is not who I am underneath, but what I do, that defines me.",  # Batman
        "That was your moment. I felt it.",                         # Original
        "Personal best. The data confirms it.",                     # Original
        "Life finds a way.",                                        # Jurassic Park
        "I am not in danger. I am the danger.",                     # Breaking Bad
        "That is what I do. I drink and I know things.",            # Game of Thrones crossover
        "It does not matter if you win by an inch or a mile. Winning is winning.", # F&F (Dom)
        "Happiness is an empty road and a full tank.",              # Vanishing Point riff
        "The driver was flawless. I would know.",                   # Rush (Lauda) riff
        "Sensors confirm optimal trajectory through all waypoints. Starfleet would be impressed.", # Star Trek techno
    ],

    "lap_degradation": [
        "The tires are talking. Time to listen.",                   # Original
        "Your eyes can deceive you. Don't trust them.",             # Obi-Wan
        "Pace yourself. The session is long.",                      # Original
        "Why do we fall? So we can learn to pick ourselves up.",    # Batman
        "You know what the worst part is? I never even learned to properly degrade.",  # Seinfeld riff
        "That is it. I am going to the bad place.",                 # Good Place crossover
    ],

    "post_session_analysis": [
        "Do, or do not. There is no try.",                          # Yoda
        "You will find that many of the truths we cling to depend greatly on our own point of view.",  # Obi-Wan
        "With great power comes great responsibility.",             # Spider-Man
        "It is not possible. No. It is necessary.",                 # Interstellar
    ],

    # ===== USB / HARDWARE =====

    "usb_connected": [
        "New hardware detected. Interesting.",                      # Original
        "One does not have to be human to have feelings, Michael.", # KITT
    ],

    "usb_disconnected": [
        "I felt a great disturbance in the Force.",                 # Obi-Wan
        "Something is missing.",                                    # Original
    ],

    # ===== FUEL =====

    "fuel_low": [
        "We are running on fumes.",                                 # Various
        "Fuel low. Find a station.",                                # Original
        "I suggest a strategic retreat to the nearest fuel depot.",  # Original
        "No gas, no gas. You know how much that costs?",            # Seinfeld riff
        "Pivot! Pivot to a gas station!",                           # Friends (Ross)
    ],

    "fuel_pressure_low": [
        "Houston, we have a problem.",                              # Apollo 13
        "Michael, I would not advise full throttle right now.",     # KITT
    ],

    # ===== GPS / POSITION / G-FORCE =====

    "gps_signal_acquired": [
        "Navigation systems online. I know where we are.",          # Original
        "GPS lock established. Tracking position.",                 # Original
        "Satellites acquired. I can see the whole track.",          # Original
        "Position confirmed. All systems nominal.",                 # Original
    ],

    "gps_signal_lost": [
        "Navigation offline. Flying blind.",                        # Original
        "I have lost visual. Going to instruments.",                # Various
        "GPS signal lost. Maintaining last known position.",        # Original
        "We are off the grid.",                                     # Original
    ],

    "extreme_lateral_g": [
        "I felt a great disturbance in the Force.",                 # Star Wars
        "That is some serious cornering force.",                    # Original
        "Physics would like a word with you.",                      # Original
        "Now this is pod racing!",                                  # Star Wars
    ],

    "perfect_apex": [
        "The line is the line.",                                    # Original
        "Textbook corner. Right through the apex.",                 # Original
        "That was the racing line. Beautiful.",                     # Original
        "Most impressive.",                                         # Vader
    ],

    # ===== WEATHER / AMBIENT CONDITIONS =====

    "pressure_falling": [
        "Barometric pressure dropping. Weather front inbound.",       # Original
        "The weather is changing. Stay alert.",                       # Original
        "Storm clouds gathering. At least metaphorically.",          # Original
        "I sense a disturbance in the atmosphere.",                   # Star Wars riff
    ],

    "pressure_rising": [
        "Pressure rising. Conditions should stabilise.",              # Original
        "The weather is clearing. Good conditions ahead.",            # Original
        "High pressure moving in. Should be a good drive.",          # Original
    ],

    "temp_dropping": [
        "Temperature falling. Grip may decrease.",                    # Original
        "It is getting cold out there. Tires will be slower to warm.", # Original
        "Winter is coming.",                                          # Game of Thrones
        "Cold front. Expect reduced grip until tires come in.",       # Original
    ],

    "temp_rising": [
        "Temperature climbing. Good for grip.",                       # Original
        "Warming up out there. Tires should come in faster.",        # Original
        "The heat is on.",                                            # Various
    ],

    "humidity_rising": [
        "Humidity rising. Watch for moisture on the surface.",        # Original
        "Getting damp out there. Reduced grip possible.",            # Original
        "Moisture in the air. Condensation risk increasing.",        # Original
    ],

    "humidity_dropping": [
        "Humidity dropping. Drier conditions ahead.",                 # Original
        "The air is drying out. Better for grip.",                   # Original
        "Less moisture. Should be good for traction.",               # Original
    ],

    # ===== RARE / EASTER EGGS (low probability) =====

    "easter_egg": [
        "I am groot.",                                              # Guardians
        "Why so serious?",                                          # Joker
        "You shall not pass!",                                      # Gandalf
        "I could do this all day.",                                 # Captain America
        "That is my secret, Captain. I am always angry.",           # Hulk
        "I am inevitable.",                                         # Thanos
        "And I... am Iron Man.",                                    # Tony Stark
        "Wakanda forever!",                                         # Black Panther
        "Frankly my dear, I do not give a damn.",                   # Gone with the Wind
        "Here is looking at you, kid.",                             # Casablanca
        "You talking to me? You talking to me?",                    # Taxi Driver
        "My mama always said, life is like a box of chocolates.",   # Forrest Gump
        "I see dead people.",                                       # Sixth Sense
    ],

    # Brain rot (very low probability — surprise factor)
    "brain_rot": [
        "No cap, that lateral G was bussin.",
        "Bro really said full send and meant it.",
        "That corner was giving main character energy.",
        "Respectfully, that lap was fire.",
        "Slay.",
        "It is giving race car. It is giving DCCD. It is giving everything.",
        "That overtake was absolutely unhinged. I am here for it.",
        "Low key, the brakes are cooked. High key, still sending it.",
        "Tell me you are a driver without telling me you are a driver.",
        "That boost hit different.",
        "Sheesh.",
        "We do not gatekeep horsepower in this vehicle.",
        "Skill issue? I think not.",
        "That was not a vibe check. That was a vibe annihilation.",
        "Rent free in the apex. Living there.",
    ],
}


# Maps alert_engine alert_type keys to event_quotes keys where they differ
ALERT_TYPE_TO_EVENT: dict[str, str] = {
    "oil_pressure_critical": "oil_pressure_low",
    "coolant_critical": "coolant_overtemp",
    "coolant_high": "coolant_overtemp",
    "fuel_pressure_critical": "fuel_pressure_low",
    "cooldown_required": "cooldown_needed",
    "warmup_engaged": "engine_cold",
    "high_g_warning": "high_lateral_g",
    "high_g_advisory": "high_lateral_g",
    "battery_low": "ecu_disconnected",
}


def get_alert_quote(alert_type: str, chance: float = 0.3) -> Optional[str]:
    """Get a quote for an alert, resolving alert_type through the mapping.

    Alert types that match event keys directly (e.g., "engine_ready") need
    no mapping entry. Mismatched keys go through ALERT_TYPE_TO_EVENT.

    Args:
        alert_type: The alert_engine alert_type string.
        chance: Probability 0.0-1.0 that a quote fires (default 30%).

    Returns:
        A random quote, or None if probability check fails or no quotes.
    """
    event_key = ALERT_TYPE_TO_EVENT.get(alert_type, alert_type)
    return get_event_quote_with_chance(event_key, chance)


def get_event_quote(event: str) -> Optional[str]:
    """Get a random quote for a vehicle event.

    Args:
        event: Event key from EVENT_QUOTES (e.g., "boost_full", "ecu_connected")

    Returns:
        A random quote string, or None if no quotes for that event.
    """
    quotes = EVENT_QUOTES.get(event)
    if not quotes:
        return None
    return random.choice(quotes)


def get_event_quote_with_chance(event: str, chance: float = 0.3) -> Optional[str]:
    """Get a quote with a probability check — not every event gets a quip.

    Args:
        event: Event key
        chance: Probability 0.0-1.0 that a quote fires (default 30%)

    Returns:
        A random quote, or None if probability check fails or no quotes.
    """
    if random.random() > chance:
        return None
    return get_event_quote(event)
