package com.example.recipeapp.data.model

import com.google.gson.annotations.SerializedName

// Те, що ми відправляємо при вході
data class LoginRequest(
    val email: String,
    val password: String
)

// Те, що ми відправляємо при реєстрації
data class RegisterRequest(
    val email: String,
    val password: String,
    @SerializedName("full_name") val fullName: String
)

// Те, що ми відправляємо для Google (id_token)
data class GoogleAuthRequest(
    @SerializedName("id_token") val idToken: String
)

// Те, що ми відправляємо при виході з акаунта
data class LogoutRequest(
    @SerializedName("refresh_token") val refreshToken: String
)

// Те, що сервер повертає (Token schema)
data class AuthResponse(
    @SerializedName("access_token") val accessToken: String,
    @SerializedName("refresh_token") val refreshToken: String,
    @SerializedName("user_id") val userId: Int,
    @SerializedName("full_name") val fullName: String?
)