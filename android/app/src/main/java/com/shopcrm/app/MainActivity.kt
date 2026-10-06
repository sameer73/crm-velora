package com.shopcrm.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color

class MainActivity : ComponentActivity() {
    private val model: CrmViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(
                colorScheme = lightColorScheme(
                    primary = Color(0xFF0B6B5C),
                    onPrimary = Color.White,
                    background = Color(0xFFEFE7D6),
                    surface = Color(0xFFFFFAF2),
                    error = Color(0xFF9D3418),
                ),
            ) {
                AppRoot(model)
            }
        }
    }
}
