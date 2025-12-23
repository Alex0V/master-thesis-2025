package com.example.recipeapp.data.model
import com.google.gson.annotations.SerializedName

// Модель Тегу (для читання)
data class DietTag(
    val id: Int,
    val name: String
)

// Модель Користувача (READ)
data class User(
    val id: Int,
    val email: String,
    @SerializedName("full_name") val fullName: String?,
    @SerializedName("family_size") val familySize: Int,
    @SerializedName("cooking_skill_level") val cookingSkillLevel: Int,
    // Приходять об'єкти!
    @SerializedName("diets") val diets: List<DietTag>
)

// Запит на оновлення (WRITE)
data class UserUpdateRequest(
    @SerializedName("full_name") val fullName: String?,
    @SerializedName("family_size") val familySize: Int?,
    @SerializedName("cooking_skill_level") val cookingSkillLevel: Int?,
    // Відправляємо ID!
    @SerializedName("diets") val dietIds: List<Int>?
)