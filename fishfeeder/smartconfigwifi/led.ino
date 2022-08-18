void autoled()
{
    if (ledcur1 >0)
    {
      ledcur1--;
      digitalWrite(0, 0);  
    }
    else
    digitalWrite(0, 1); 
}
