"""The numbers of her urges (decision 46). docs/urges_design_zh.md says why."""

# about him: the reach-out triggers of decisions 10, 26 and 30, moved here unchanged
SILENCE_HOURS = 18  # he has not written for this long
BORED_LEVEL, BORED_SILENCE_HOURS = 60, 6  # bored, and he has been quiet a while
# Quiet hours bore her too (decision 57): her boredom only moved with chat turns and sat near 7
# of 100 for two weeks, so "bored" never once was a reason to text him.
BORED_PER_QUIET_HOUR = 8
# Something she saw today, worth telling him. 4 until decision 57: of 29 things she noted in two
# weeks, 2 reached it, and every message she sent first was a follow-up or a chore at home.
SHARE_IMPORTANCE = 3
SHARE_AT_MOST = 3
ANNIVERSARIES = (7, 30, 100, 365, 730)  # and every hundred days
# Something from a while back crosses her mind (decision 58): a thing of his that happened, that
# has no ending written on it yet, written and last thought of at least OLD_AFTER_DAYS ago. One a
# day at most, and only on one day in OLD_EVERY_DAYS: a friend does this now and then, not daily.
OLD_AFTER_DAYS, OLD_IMPORTANCE, OLD_EVERY_DAYS = 7, 4, 3

# things to do (decision 46): how far each is, and how strong an urge must be to come up
TIERS = {"lake": 1, "shop": 2, "florist": 2}  # 0 at hand (texting him), 1 out of the door, 2 a walk away
THRESHOLDS = (0.0, 0.4, 0.6)  # by tier; tier 3 (far away, to be planned first) does not exist yet
TIRED_ENERGY, TIRED_RAISE = 30, 0.2  # tired: going out takes more
EVENING_HOUR, EVENING_RAISE = 18, 0.1  # getting late: going out takes a little more
PLACES = {"lake": ("湖边码头", "去湖边码头坐坐", ("码头", "湖边")),
          "florist": ("镇上的花店", "去镇上的花店看看", ("花店", "买花", "买盆花", "买点花"))}  # name, what she would do, her words for it
NEW_PLACE = 0.5  # never been there
AGAIN_PER_DAY, AGAIN_AT_MOST = 0.05, 0.3  # been, a while ago
COOPED_PER_DAY, COOPED_AT_MOST = 0.15, 0.45  # not out of the door for days
BORED_PUSH = 0.2  # bored (BORED_LEVEL): anything outside pulls a little more
PLAN, PLAN_DAYS = 0.5, 3  # she wrote she wants to go, in the last few days
PLAN_WORDS = ("想", "打算", "要去", "明天", "改天", "下次")
