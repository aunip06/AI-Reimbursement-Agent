from datetime import datetime


def match_receipt(receipt, expenses):

    matches = []

    for expense in expenses:

        score = 0

        # Amount Match
        if receipt["amount"] != "":
            try:
                if int(receipt["amount"]) == int(expense["amount"]):
                    score += 50
            except:
                pass

        # Date Match
        if receipt["date"] != "":
            try:
                receipt_date = datetime.strptime(
                    receipt["date"],
                    "%d %B %Y"
                ).date()

                if receipt_date == expense["date"].date():
                    score += 30
            except:
                pass

        # Merchant / Description Match
        if receipt["message"]:

            receipt_words = receipt["message"].lower().split()

            description = str(expense["description"]).lower()

            common = 0

            for word in receipt_words:
                if word in description:
                    common += 1

            score += common * 10

        matches.append(
            {
                "score": score,
                "expense": expense
            }
        )

    matches.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return matches[0]