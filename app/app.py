import os
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

app = Flask(__name__)


# Connect to the Dishcovery database
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


# Display the homepage
@app.route("/")
def home():
    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total FROM Recipes")
        recipe_count = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT recipe_id, recipe_name, cooking_time, difficulty
            FROM Recipes
            ORDER BY recipe_name
        """)
        recipes = cursor.fetchall()

        # Fetch all ingredients for the ingredient selector
        cursor.execute("""
            SELECT ingredient_id, ingredient_name
            FROM Ingredients
            ORDER BY ingredient_name
        """)
        ingredients = cursor.fetchall()

        cursor.close()

        return render_template(
        "index.html",
        recipe_count=recipe_count,
        recipes=recipes,
        ingredients=ingredients
    )
    
    except mysql.connector.Error:
        app.logger.exception("Could not load the homepage.")
        return "Unable to retrieve recipes. Please check the database connection.", 500

    finally:
        if connection is not None and connection.is_connected():
            connection.close()


# Find recipes using available ingredients
@app.route("/find-recipes", methods=["POST"])
def find_recipes():
    data = request.get_json(silent=True) or {}
    ingredients = data.get("ingredients", [])

    if not isinstance(ingredients, list):
        return jsonify({"error": "Ingredients must be provided as a list."}), 400

    ingredients = list(dict.fromkeys(
        item.strip().lower()
        for item in ingredients
        if isinstance(item, str) and item.strip()
    ))

    if not ingredients:
        return jsonify({"error": "Please select at least one ingredient."}), 400

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Find recipes containing at least one selected ingredient.
        placeholders = ", ".join(["%s"] * len(ingredients))

        query = f"""
            SELECT
                r.recipe_id,
                r.recipe_name,
                r.cooking_time,
                r.difficulty,
                COUNT(DISTINCT CASE
                    WHEN LOWER(i.ingredient_name) IN ({placeholders})
                    THEN i.ingredient_id
                END) AS matched_count,
                COUNT(DISTINCT ri.ingredient_id) AS total_ingredients,


                COUNT(DISTINCT CASE
                    WHEN LOWER(i.ingredient_name) NOT IN ({placeholders})
                    THEN i.ingredient_id
                END) AS missing_count,


                GROUP_CONCAT(
                    DISTINCT CASE
                        WHEN LOWER(i.ingredient_name) NOT IN ({placeholders})
                        THEN i.ingredient_name
                    END
                    ORDER BY i.ingredient_name
                    SEPARATOR ', '
                ) AS missing_ingredients
            FROM Recipes r
            JOIN Recipe_Ingredients ri
                ON r.recipe_id = ri.recipe_id
            JOIN Ingredients i
                ON ri.ingredient_id = i.ingredient_id
            GROUP BY
                r.recipe_id,
                r.recipe_name,
                r.cooking_time,
                r.difficulty
            HAVING matched_count > 0
            ORDER BY
                (matched_count = total_ingredients) DESC,
                matched_count DESC,
                r.recipe_name
        """

        parameters = ingredients + ingredients + ingredients
        cursor.execute(query, parameters)
        recipes = cursor.fetchall()

        cursor.close()

        return jsonify({"recipes": recipes})

    except mysql.connector.Error:
        app.logger.exception("Recipe search failed.")
        return jsonify({"error": "Unable to search recipes right now."}), 500

    finally:
        if connection is not None and connection.is_connected():
            connection.close()


# Find recipes by category
@app.route("/category/<category_name>")
def find_by_category(category_name):
    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                r.recipe_id,
                r.recipe_name,
                r.cooking_time,
                r.difficulty
            FROM Recipes r
            JOIN Recipe_Categories rc
                ON r.recipe_id = rc.recipe_id
            JOIN Categories c
                ON rc.category_id = c.category_id
            WHERE LOWER(c.category_name) = LOWER(%s)
            ORDER BY r.recipe_name
        """, (category_name,))

        recipes = cursor.fetchall()

        cursor.close()

        return render_template(
    "recipe_results.html",
    category=category_name.title(),
    recipes=recipes
)

    except mysql.connector.Error:
        app.logger.exception("Category search failed.")
        return jsonify({
            "error": "Unable to retrieve recipes for this category."
        }), 500

    finally:
        if connection is not None and connection.is_connected():
            connection.close()



# Display individual recipe details
@app.route("/recipe/<int:recipe_id>")
def recipe_details(recipe_id):
    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Retrieve the selected recipe
        cursor.execute("""
            SELECT
                recipe_id,
                recipe_name,
                cooking_time,
                difficulty,
                instructions
            FROM Recipes
            WHERE recipe_id = %s
        """, (recipe_id,))

        recipe = cursor.fetchone()

        if recipe is None:
            cursor.close()
            return "Recipe not found.", 404

        # Retrieve ingredients required for this recipe
        cursor.execute("""
            SELECT i.ingredient_name
            FROM Ingredients i
            JOIN Recipe_Ingredients ri
                ON i.ingredient_id = ri.ingredient_id
            WHERE ri.recipe_id = %s
            ORDER BY i.ingredient_name
        """, (recipe_id,))

        ingredients = cursor.fetchall()

        cursor.close()

        return render_template(
            "recipe_details.html",
            recipe=recipe,
            ingredients=ingredients
        )

    except mysql.connector.Error:
        app.logger.exception("Could not retrieve recipe details.")
        return "Unable to retrieve recipe details.", 500

    finally:
        if connection is not None and connection.is_connected():
            connection.close()



# Start the application
if __name__ == "__main__":
    app.run(debug=False)

