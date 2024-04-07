import os

from groq import Groq

client = Groq(
    api_key=os.environ.get("YOUR_GROQ_API_KEY"),
)

# Create a groqument from local PDF
grocument = client.documents.create(
    data={
        "type": "pdf",
        "content": "./FoodshowQA.pdf",
    },
)


def groqument(groqument):
    return client.documents.create(
        data=groqument,
    )

def groq_query(groq_query):
    return client.queries.create(
        query=groq_query,
    )

# Get user input as groq_query
groq_query = input("Enter your groq query: ")


chat_completion = client.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": "{grocument}",
        },
        {
            "role": "user",
            "content": "Act as an authority on all the information in {groqument} and address user's {groq_query}.",
        }
    ],
    model="mixtral-8x7b-32768",
)

print(chat_completion.choices[0].message.content)