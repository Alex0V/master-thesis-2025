package com.example.recipeapp.data.api

import com.example.recipeapp.data.model.AuthResponse
import com.example.recipeapp.data.model.GoogleAuthRequest
import com.example.recipeapp.data.model.LoginRequest
import com.example.recipeapp.data.model.LogoutRequest
import com.example.recipeapp.data.model.RecipeDetails
import com.example.recipeapp.data.model.RecipeSummary
import com.example.recipeapp.data.model.RegisterRequest
import com.example.recipeapp.data.model.TagGroupResponse
import com.example.recipeapp.data.model.User
import com.example.recipeapp.data.model.UserUpdateRequest
import com.example.recipeapp.data.model.DietTag
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.Call
import retrofit2.http.DELETE
import retrofit2.http.PATCH
import retrofit2.http.Path
import retrofit2.http.Query

interface RecipeApiService {
    // --- МЕТОДИ AUTH ---
    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): AuthResponse

    @POST("auth/register")
    suspend fun register(@Body request: RegisterRequest): AuthResponse

    @POST("auth/google")
    suspend fun googleLogin(@Body request: GoogleAuthRequest): AuthResponse

    @POST("auth/logout")
    suspend fun logout(@Body request: LogoutRequest): Unit // Unit означає, що нам не важлива відповідь

    // Для Refresh Token використовуємо Call (синхронний запит),
    // бо Authenticator працює в синхронному потоці OkHttp
    @POST("auth/refresh")
    fun refreshToken(@Body body: Map<String, String>): Call<AuthResponse>

    // --- ІСНУЮЧИЙ МЕТОД ---
    @GET("recipes/recommendations")
    suspend fun getRecommendations(): List<RecipeSummary>

    @GET("recipes/{id}")
    suspend fun getRecipeDetails(@Path("id") id: Int): RecipeDetails

    // 1. Отримання категорій фільтрів
    @GET("recipes/tags")
    suspend fun getRecipeTags(): List<TagGroupResponse>

    // 2. Пошук рецептів (текст + фільтри)
    @GET("recipes/search")
    suspend fun searchRecipes(
        @Query("query") query: String?,
        @Query("tag_name") tagName: String?,
        @Query("tag_type") tagType: String?
    ): List<RecipeSummary> // Використовуйте ту модель, яка у вас на картках

    @GET("favorites/")
    suspend fun getFavoriteRecipes(): List<RecipeSummary> // Використовуємо ту ж модель, що і в Feed

    @POST("favorites/{id}")
    suspend fun addToFavorites(@Path("id") id: Int): Any // Any або Response<Unit>

    @DELETE("favorites/{id}")
    suspend fun removeFromFavorites(@Path("id") id: Int): Any

    @GET("users/me")
    suspend fun getProfile(): User

    @PATCH("users/me")
    suspend fun updateProfile(@Body body: UserUpdateRequest): User

    @GET("tags/diets") // Перевірте, чи у вас в API це "diets" чи "tags/diets"
    suspend fun getDiets(
        @Query("min_recipes") minRecipes: Int = 0
    ): List<DietTag>
}