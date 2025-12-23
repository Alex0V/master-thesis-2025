package com.example.recipeapp.ui.components

import android.util.Log
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.example.recipeapp.data.model.RecipeSummary

// 👇 Картка рецепта (без змін)
@Composable
fun RecipeItem(
    recipe: RecipeSummary, // або Recipe
    onClick: () -> Unit // 👈 Додайте це
) {
    Card(
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
        modifier = Modifier.fillMaxWidth().height(220.dp)
            // 👇 ТУТ МАЄ БУТИ КЛІК
            .clickable {
                Log.d("CLICK", "Натиснуто на рецепт: ${recipe.id}") // Додайте цей лог для перевірки
                onClick()
            },
    ) {
        Column {
            // 1. Зображення
            AsyncImage(
                model = ImageRequest.Builder(LocalContext.current)
                    .data(recipe.imageUrl)
                    .crossfade(true)
                    // 👇 ВАЖЛИВО: Кажемо Coil завантажити картинку розміром не більше 300x300 пікселів.
                    // Це миттєво зменшує навантаження на процесор у 10-20 разів.
                    // Для вашої картки цього більш ніж достатньо.
                    .size(300, 300)
                    // Або використовуйте .size(ViewSizeResolver(rootView)) для автовизначення,
                    // але жорстке обмеження (300) працює швидше і надійніше для списків.
                    .build(),
                contentDescription = recipe.title,
                contentScale = ContentScale.Crop,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(120.dp)
                    // Додайте фон, щоб поки картинка вантажиться, місце не було пустим
                    .background(Color.LightGray)
            )
            // 2. Текст (Назва і деталі)
            Column(
                modifier = Modifier
                    .padding(12.dp)
                    .fillMaxSize() // Заповнює решту місця
            ) {
                Text(
                    text = recipe.title,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    maxLines = 2,
                    minLines = 2,
                    overflow = TextOverflow.Ellipsis
                )

                Spacer(modifier = Modifier.weight(1f)) // Притискає інфо до низу

                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "⏱ ${recipe.totalTime} хв",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.secondary
                    )
                    Spacer(modifier = Modifier.weight(1f))
                    Text(
                        text = recipe.difficulty,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.tertiary
                    )
                }
            }
        }
    }
}