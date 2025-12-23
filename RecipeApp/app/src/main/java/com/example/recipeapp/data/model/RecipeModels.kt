package com.example.recipeapp.data.model

import com.google.gson.annotations.SerializedName

data class RecipeSummary(
    val id: Int,
    val title: String,

    // Ми кажемо: "В JSON це поле називається image_s3_path, але тут я хочу imageUrl"
    @SerializedName("image_s3_path")
    val imageUrl: String?,

    val difficulty: String,

    @SerializedName("prep_time_min")
    val prepTime: Int,

    @SerializedName("cook_time_min")
    val cookTime: Int,

    @SerializedName("total_time")
    val totalTime: Int // Це поле ми будемо показувати в картці!
)


// Цей клас приймає повний JSON детального перегляду
data class RecipeDetails(
    val id: Int,
    val title: String,
    @SerializedName("image_s3_path") val imageUrl: String?,
    @SerializedName("difficulty") val difficulty: String,
    @SerializedName("prep_time_min") val prepTime: Int?,
    @SerializedName("cook_time_min") val cookTime: Int?,
    @SerializedName("total_time") val totalTime: Int?,
    @SerializedName("portions_num") val portions: Double?,
    val nutrition: Nutrition?,

    // 👇 ВАЖЛИВО: Мапимо JSON поле "ingredients" у змінну "sections"
    @SerializedName("ingredients")
    val sections: List<IngredientSection>,
    @SerializedName("is_favorite")
    val isFavorite: Boolean = false,
    val instructions: List<InstructionStep>
)

// 1. Елемент інгредієнта
data class IngredientItem(
    val name: String,
    val amount: Double,
    val unit: String,
    @SerializedName("is_optional") val isOptional: Boolean
)

// 2. Секція (Група)
data class IngredientSection(
    val name: String, // Наприклад: "Основні", "Тісто", "Крем"
    @SerializedName("ingredients") val items: List<IngredientItem>
)

// 3. Інструкція
data class InstructionStep(
    @SerializedName("step_number") val stepNumber: Int,
    val title: String?,
    val description: String
)

// 4. Нутрієнти
data class Nutrition(
    val calories: Double,
    val proteins: Double,
    val fats: Double,
    val carbs: Double
)

data class TagGroupResponse(
    @SerializedName("category") val category: String,
    @SerializedName("tags") val tags: List<String>
)