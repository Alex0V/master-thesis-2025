package com.example.recipeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.example.recipeapp.data.api.RecipeApiService
import com.example.recipeapp.viewmodel.SearchViewModel
import com.example.recipeapp.viewmodel.SearchViewModelFactory
// 👇 Ваш компонент картки (змініть назву, якщо у вас інша)
import com.example.recipeapp.ui.components.RecipeItem

@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
fun SearchScreen(
    navController: NavController,
    apiService: RecipeApiService
) {
    val viewModel: SearchViewModel = viewModel(
        factory = SearchViewModelFactory(apiService)
    )

    val searchQuery by viewModel.searchQuery.collectAsState()
    val tagGroups by viewModel.tagGroups.collectAsState()
    val selectedTag by viewModel.selectedTag.collectAsState()
    val searchResults by viewModel.searchResults.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {

        // --- ПОЛЕ ПОШУКУ ---
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { viewModel.onQueryChange(it) },
            modifier = Modifier.fillMaxWidth(),
            placeholder = { Text("Назва, інгредієнт...") },
            leadingIcon = { Icon(Icons.Default.Search, null) },
            trailingIcon = {
                if (searchQuery.isNotEmpty() || selectedTag != null) {
                    IconButton(onClick = { viewModel.clearSearch() }) {
                        Icon(Icons.Default.Clear, null)
                    }
                }
            },
            shape = RoundedCornerShape(12.dp),
            singleLine = true
        )

        // Індикатор завантаження
        if (isLoading) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth().height(2.dp).padding(top = 4.dp))
        } else {
            Spacer(modifier = Modifier.height(6.dp))
        }

        Spacer(modifier = Modifier.height(10.dp))

        // --- ЛОГІКА ВІДОБРАЖЕННЯ ---

        // Стан 1: Показуємо категорії (якщо нічого не шукаємо)
        if (searchQuery.isEmpty() && selectedTag == null) {
            LazyColumn(modifier = Modifier.fillMaxSize()) {
                // Сортування: Сніданки перші
                val sortedGroups = tagGroups.sortedBy { group ->
                    when(group.category) {
                        "meal_type" -> 1
                        "diet" -> 2
                        "cuisine" -> 3
                        "occasion" -> 4
                        else -> 5
                    }
                }

                items(sortedGroups) { group ->
                    Text(
                        text = mapCategoryToUkrainian(group.category),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(vertical = 8.dp)
                    )

                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        group.tags.forEach { tag ->
                            FilterChip(
                                selected = false,
                                onClick = { viewModel.onTagSelected(group.category, tag) },
                                label = { Text(tag) }
                            )
                        }
                    }
                    HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp), thickness = 0.5.dp)
                }
            }
        }
        // Стан 2: Показуємо результати
        else {
            // Відображення вибраного фільтра
            selectedTag?.let { (cat, tag) ->
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(bottom = 8.dp)) {
                    Text("Фільтр:", style = MaterialTheme.typography.bodyMedium)
                    Spacer(modifier = Modifier.width(8.dp))
                    InputChip(
                        selected = true,
                        onClick = { viewModel.onTagSelected(cat, tag) },
                        label = { Text(tag) },
                        trailingIcon = { Icon(Icons.Default.Clear, null, Modifier.size(16.dp)) }
                    )
                }
            }

            if (searchResults.isEmpty() && !isLoading) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("Нічого не знайдено 😕", color = Color.Gray)
                }
            } else {
                LazyVerticalGrid(
                    columns = GridCells.Fixed(2),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(searchResults) { recipe ->
                        RecipeItem(
                            recipe = recipe,
                            onClick = { navController.navigate("recipe_details/${recipe.id}") }
                        )
                    }
                }
            }
        }
    }
}

fun mapCategoryToUkrainian(category: String): String {
    return when (category) {
        "meal_type" -> "🍽️ Час прийому їжі"
        "diet" -> "🥗 Дієта"
        "cuisine" -> "🌍 Кухні світу"
        "occasion" -> "🎉 Події"
        "dish_type" -> "🍲 Тип страви"
        else -> category.replaceFirstChar { it.uppercase() }
    }
}